import logging
import json
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
                    client_data = dict(data)
                    # Mask rival supplier in new bid notification if rival placed it
                    if client_data.get("supplier_id") != client_supplier_id:
                        if client_data.get("rank") != 1:
                            client_data["total"] = None
                            client_data["freight_charges"] = None
                        client_data["supplier_name"] = "Masked Supplier"
                        client_data["supplier_code"] = "MASKED"
                    # Mask rankings list
                    if "rankings" in client_data:
                        masked_rankings = []
                        for r in client_data["rankings"]:
                            is_mine = (r.get("supplier_id") == client_supplier_id)
                            if is_mine:
                                masked_rankings.append(dict(r))
                            elif r.get("rank") == 1:
                                # L1 price is visible, name masked
                                masked_rankings.append({
                                    "rank": 1,
                                    "supplier_id": r.get("supplier_id"),
                                    "supplier_name": "L1 Leader (Masked)",
                                    "supplier_code": "L1",
                                    "total": r.get("total"),
                                })
                            else:
                                masked_rankings.append({
                                    "rank": r.get("rank"),
                                    "supplier_id": r.get("supplier_id"),
                                    "supplier_name": f"Rank {r.get('rank')} (Masked)",
                                    "supplier_code": f"L{r.get('rank')}",
                                    "total": None,
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
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_to_rfq(rfq_id, event_type, data), loop)
            else:
                loop.run_until_complete(self.broadcast_to_rfq(rfq_id, event_type, data))
        except Exception as e:
            logger.debug("Could not schedule sync broadcast: %s", e)


ws_manager = WebSocketManager()

