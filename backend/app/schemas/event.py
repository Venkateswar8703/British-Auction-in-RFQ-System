from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.enums import AuctionEventType


class AuctionEventOut(BaseModel):
    id: str
    rfq_id: str
    bid_id: Optional[str] = None
    event_type: AuctionEventType
    payload: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebSocketAuctionMessage(BaseModel):
    event_type: str
    rfq_id: str
    server_time: datetime
    data: Dict[str, Any]
