from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.enums import RFQStatus, TriggerType, InvitationStatus
from app.schemas.supplier import SupplierSimpleOut
from app.schemas.bid import SupplierRankOut, BidOut


class AuctionConfigBase(BaseModel):
    trigger_window_minutes: int = Field(default=10, gt=0, description="X: Trigger window in minutes")
    extension_minutes: int = Field(default=5, gt=0, description="Y: Extension duration in minutes")
    trigger_type: TriggerType = Field(default=TriggerType.L1_CHANGE)
    min_decrement: Optional[Decimal] = Field(default=Decimal("0.00"), ge=0, description="Optional minimum bid decrement")


class AuctionConfigOut(AuctionConfigBase):
    id: str
    rfq_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RFQInvitationOut(BaseModel):
    id: str
    supplier_id: str
    supplier: SupplierSimpleOut
    status: InvitationStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuctionExtensionOut(BaseModel):
    id: str
    rfq_id: str
    triggering_bid_id: Optional[str] = None
    previous_close: datetime
    new_close: datetime
    trigger_type: str
    reason: str
    is_clamped: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RFQCreate(BaseModel):
    reference_id: Optional[str] = Field(default=None, max_length=64)
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    origin: str = Field(..., min_length=2, max_length=255)
    destination: str = Field(..., min_length=2, max_length=255)
    pickup_date: datetime
    bid_start: datetime
    bid_close: datetime
    forced_close: datetime
    trigger_window_minutes: int = Field(default=10, gt=0)
    extension_minutes: int = Field(default=5, gt=0)
    trigger_type: TriggerType = Field(default=TriggerType.L1_CHANGE)
    min_decrement: Optional[Decimal] = Field(default=Decimal("0.00"), ge=0)
    invited_supplier_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.bid_close <= self.bid_start:
            raise ValueError("bid_close must be strictly after bid_start")
        if self.forced_close <= self.bid_close:
            raise ValueError("forced_close must be strictly after bid_close")
        if self.pickup_date <= self.bid_close:
            raise ValueError("pickup_date must be strictly after bid_close")
        return self


class RFQUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    pickup_date: Optional[datetime] = None
    bid_start: Optional[datetime] = None
    bid_close: Optional[datetime] = None
    forced_close: Optional[datetime] = None
    trigger_window_minutes: Optional[int] = Field(None, gt=0)
    extension_minutes: Optional[int] = Field(None, gt=0)
    trigger_type: Optional[TriggerType] = None
    invited_supplier_ids: Optional[List[str]] = None


class RFQOut(BaseModel):
    id: str
    reference_id: str
    title: str
    description: Optional[str] = None
    origin: str
    destination: str
    pickup_date: datetime
    bid_start: datetime
    bid_close: datetime
    effective_close: datetime
    forced_close: datetime
    status: RFQStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    config: Optional[AuctionConfigOut] = None
    invitations: List[RFQInvitationOut] = Field(default_factory=list)
    
    lowest_bid_total: Optional[Decimal] = None
    total_bids_count: int = 0
    participating_suppliers_count: int = 0
    is_invited: Optional[bool] = None
    my_latest_bid: Optional[BidOut] = None
    my_rank: Optional[int] = None
    server_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RFQDetailOut(RFQOut):
    rankings: List[SupplierRankOut] = Field(default_factory=list)
    recent_extensions: List[AuctionExtensionOut] = Field(default_factory=list)
    my_bid_history: List[BidOut] = Field(default_factory=list)
