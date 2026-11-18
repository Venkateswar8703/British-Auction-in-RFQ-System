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
        # Maps rfq_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, rfq_id: str, websocket: WebSocket):
        await websocket.accept()
        if rfq_id not in self.active_connections:
            self.active_connections[rfq_id] = set()
        self.active_connections[rfq_id].add(websocket)
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
            self.active_connections[rfq_id].discard(websocket)
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
        payload = {
            "event_type": event_type,
            "rfq_id": rfq_id,
            "server_time": server_now.isoformat(),
            "data": data,
        }
        text = json.dumps(payload, default=json_serializer)

        dead_sockets = set()
        for connection in list(self.active_connections[rfq_id]):
            try:
                await connection.send_text(text)
            except Exception as e:
                logger.warning("Error broadcasting to WS client on RFQ %s: %s", rfq_id, e)
                dead_sockets.add(connection)

        for dead in dead_sockets:
            self.disconnect(rfq_id, dead)


ws_manager = WebSocketManager()

