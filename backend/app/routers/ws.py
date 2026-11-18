import logging
import json
import asyncio
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

from app.config import settings
from app.database import SessionLocal
from app.models.entities import User, RFQ, RFQInvitation
from app.models.enums import UserRole
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/rfqs/{rfq_id}")
async def websocket_auction_endpoint(
    websocket: WebSocket, 
    rfq_id: str,
    token: Optional[str] = Query(None),
    ticket: Optional[str] = Query(None),
):
    auth_token = token or ticket
    if not auth_token:
        # First-message authentication flow
        await websocket.accept()
        try:
            raw_init = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            init_json = json.loads(raw_init)
            if init_json.get("action") == "AUTH":
                auth_token = init_json.get("token") or init_json.get("ticket")
        except Exception:
            await websocket.close(code=4001, reason="Authentication timeout or invalid message")
            return

    if not auth_token:
        await websocket.close(code=4001, reason="Authentication token required")
        return

    try:
        payload = jwt.decode(
            auth_token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        role = payload.get("role")
        supplier_id = payload.get("supplier_id")
        user_id = payload.get("sub")

        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

        if role == UserRole.SUPPLIER.value:
            # Check invitation in database
            db = SessionLocal()
            try:
                if not supplier_id:
                    user_record = db.query(User).filter(User.id == user_id).first()
                    if user_record:
                        supplier_id = user_record.supplier_id

                # Resolve rfq
                rfq = db.query(RFQ).filter((RFQ.id == rfq_id) | (RFQ.reference_id == rfq_id)).first()
                if not rfq:
                    await websocket.close(code=4004, reason="RFQ not found")
                    return

                invitation = (
                    db.query(RFQInvitation)
                    .filter(RFQInvitation.rfq_id == rfq.id, RFQInvitation.supplier_id == supplier_id)
                    .first()
                )
                if not invitation:
                    logger.warning(
                        "Refusing WebSocket connection: Supplier %s not invited to RFQ %s",
                        supplier_id,
                        rfq.reference_id,
                    )
                    await websocket.close(code=4003, reason="Forbidden: Carrier not invited to this RFQ")
                    return
            finally:
                db.close()
    except JWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    client_info = {"role": role, "supplier_id": supplier_id, "user_id": user_id}
    await ws_manager.connect(rfq_id, websocket, client_info=client_info)
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                action = msg.get("action")
                if action == "PING":
                    now = datetime.now(timezone.utc)
                    await ws_manager.send_personal_message(
                        {
                            "event_type": "PONG",
                            "rfq_id": rfq_id,
                            "server_time": now.isoformat(),
                            "client_time": msg.get("client_time"),
                            "data": {"timestamp_ms": int(now.timestamp() * 1000)},
                        },
                        websocket,
                    )
                elif action == "CLOCK_SYNC":
                    now = datetime.now(timezone.utc)
                    await ws_manager.send_personal_message(
                        {
                            "event_type": "CLOCK_SYNC",
                            "rfq_id": rfq_id,
                            "server_time": now.isoformat(),
                            "client_sent_ms": msg.get("client_sent_ms"),
                            "server_received_ms": int(now.timestamp() * 1000),
                        },
                        websocket,
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(rfq_id, websocket)
    except Exception as e:
        logger.warning("WebSocket error on RFQ %s: %s", rfq_id, e)
        ws_manager.disconnect(rfq_id, websocket)

