import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class WebSocketManager:
    def __init__(self):
        # Maps rfq_id -> dict of websocket -> client_info
        self.active_connections: Dict[str, Dict[WebSocket, Dict[str, Any]]] = {}

    async def connect(self, rfq_id: str, websocket: WebSocket, client_info: Dict[str, Any] = None):
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        from starlette.websockets import WebSocketState
        if websocket.client_state != WebSocketState.CONNECTED:
            await websocket.accept()
        if rfq_id not in self.active_connections:
            self.active_connections[rfq_id] = {}
        self.active_connections[rfq_id][websocket] = client_info or {}
        logger.info("Client connected to RFQ %s WS room. Total in room: %d", rfq_id, len(self.active_connections[rfq_id]))

        # Send initial clock sync handshake
        server_now = datetime.now(timezone.utc)
        await self.send_personal_message(
            {
                "event_type": "CLOCK_SYNC",
                "rfq_id": rfq_id,
                "server_time": server_now.isoformat(),
                "data": {"timestamp_ms": int(server_now.timestamp() * 1000)},
            },
            websocket,
        )

    def disconnect(self, rfq_id: str, websocket: WebSocket):
        if rfq_id in self.active_connections:
            self.active_connections[rfq_id].pop(websocket, None)
            if not self.active_connections[rfq_id]:
                del self.active_connections[rfq_id]
        logger.info("Client disconnected from RFQ %s WS room", rfq_id)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message, default=json_serializer))
        except Exception as e:
            logger.warning("Failed to send personal WS message: %s", e)

    async def broadcast_to_rfq(self, rfq_id: str, event_type: str, data: Dict[str, Any]):
        """Broadcasts a typed real-time payload with the exact server timestamp to all room clients."""
        if rfq_id not in self.active_connections:
            return

        server_now = datetime.now(timezone.utc)
        bid_visibility = data.get("bid_visibility", "OPEN")

        dead_sockets = set()
        for connection, client_info in list(self.active_connections[rfq_id].items()):
            try:
                # Prepare personalized payload if masked
                if bid_visibility == "MASKED" and client_info.get("role") == "supplier":
                    client_supplier_id = client_info.get("supplier_id")
                    client_data = json.loads(json.dumps(data, default=json_serializer))

                    # Event-specific sanitization for MASKED supplier
                    if event_type == "BID_SUBMITTED":
                        if client_data.get("supplier_id") != client_supplier_id:
                            client_data["supplier_id"] = "competitor"
                            client_data["supplier_name"] = "Competitor"
                            client_data["carrier_name"] = "Masked Carrier"
                            client_data["freight_charges"] = None
                            client_data["origin_charges"] = None
                            client_data["destination_charges"] = None
                            client_data["total"] = None
                    elif event_type == "L1_CHANGED":
                        if client_data.get("new_l1_supplier_id") != client_supplier_id:
                            client_data["new_l1_supplier_id"] = "competitor"
                        if client_data.get("previous_l1_supplier_id") != client_supplier_id:
                            client_data["previous_l1_supplier_id"] = "competitor"
                        client_data["notification_text"] = "New leading bid (L1) placed"
                    elif event_type == "RANK_CHANGED":
                        prev_r = client_data.get("previous_ranks", {})
                        new_r = client_data.get("new_ranks", {})
                        my_prev = prev_r.get(client_supplier_id)
                        my_new = new_r.get(client_supplier_id)
                        client_data["previous_ranks"] = {"your_rank": my_prev} if my_prev else {}
                        client_data["new_ranks"] = {"your_rank": my_new} if my_new else {}
                        client_data["notification_text"] = "Auction ranking ladder shifted"
                    elif event_type in ["EXTENSION_APPLIED", "EXTENSION_CAPPED"]:
                        ext_min = client_data.get("extension_minutes", 5)
                        client_data["triggering_bid_id"] = None
                        client_data["reason"] = f"Auction extended by {ext_min}m due to competitive bid inside trigger window"
                        client_data["notification_text"] = f"Auction deadline extended by {ext_min} minutes"
                    elif event_type == "NEW_BID":
                        if client_data.get("supplier_id") != client_supplier_id:
                            client_data["supplier_id"] = "competitor"
                            client_data["supplier_name"] = "Masked Supplier"
                            client_data["supplier_code"] = "MASKED"
                            client_data["carrier_name"] = "Masked Carrier"
                            client_data["freight_charges"] = None
                            client_data["origin_charges"] = None
                            client_data["destination_charges"] = None
                            client_data["total"] = None
                        if "extension_details" in client_data:
                            client_data["extension_details"]["reason"] = "Dynamic extension applied due to competitive bid"
                        if "rankings" in client_data:
                            masked_rankings = []
                            for r in client_data["rankings"]:
                                is_mine = (r.get("supplier_id") == client_supplier_id)
                                if is_mine:
                                    masked_rankings.append(dict(r))
                                else:
                                    masked_rankings.append({
                                        "rank": r.get("rank"),
                                        "supplier_id": f"competitor-{r.get('rank')}",
                                        "supplier_name": "L1 Leader (Masked)" if r.get("rank") == 1 else f"Rank {r.get('rank')} (Masked)",
                                        "supplier_code": "L1" if r.get("rank") == 1 else f"L{r.get('rank')}",
                                        "carrier_name": "Masked Carrier",
                                        "freight_charges": None,
                                        "origin_charges": None,
                                        "destination_charges": None,
                                        "total": r.get("total") if r.get("rank") == 1 else None,
                                    })
                            client_data["rankings"] = masked_rankings

                    payload = {
                        "event_type": event_type,
                        "rfq_id": rfq_id,
                        "server_time": server_now.isoformat(),
                        "data": client_data,
                    }
                else:
                    payload = {
                        "event_type": event_type,
                        "rfq_id": rfq_id,
                        "server_time": server_now.isoformat(),
                        "data": data,
                    }

                await connection.send_text(json.dumps(payload, default=json_serializer))
            except Exception as e:
                logger.warning("Error broadcasting to WS client on RFQ %s: %s", rfq_id, e)
                dead_sockets.add(connection)

        for dead in dead_sockets:
            self.disconnect(rfq_id, dead)

    def broadcast_to_rfq_sync(self, rfq_id: str, event_type: str, data: Dict[str, Any]):
        """Thread-safe synchronous wrapper to broadcast from background threads to the main event loop."""
        import asyncio
        loop = getattr(self, "_loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_to_rfq(rfq_id, event_type, data), loop)
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_to_rfq(rfq_id, event_type, data), loop)
            else:
                loop.run_until_complete(self.broadcast_to_rfq(rfq_id, event_type, data))
        except Exception as e:
            logger.debug("Could not schedule sync broadcast: %s", e)


ws_manager = WebSocketManager()

