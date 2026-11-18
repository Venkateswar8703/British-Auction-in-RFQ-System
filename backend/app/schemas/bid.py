from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


class BidCreate(BaseModel):
    freight_charges: Decimal = Field(..., gt=0, description="Freight charges (USD)")
    origin_charges: Decimal = Field(..., ge=0, description="Origin charges (USD)")
    destination_charges: Decimal = Field(..., ge=0, description="Destination charges (USD)")
    transit_time_days: int = Field(..., gt=0, description="Transit time in days")
    quote_validity_date: datetime = Field(..., description="Date until which quote is valid")
    carrier_name: str = Field(..., min_length=1, max_length=255, description="Operating carrier name")
    idempotency_key: Optional[str] = Field(None, description="Client idempotency key")


class BidOut(BaseModel):
    id: str
    rfq_id: str
    supplier_id: str
    supplier_name: Optional[str] = None
    supplier_code: Optional[str] = None
    submitted_by: str
    submitter_name: Optional[str] = None
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total: Decimal
    transit_time_days: int
    quote_validity_date: datetime
    carrier_name: str
    idempotency_key: Optional[str] = None
    created_at: datetime
    rank: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SupplierRankOut(BaseModel):
    rank: int
    supplier_id: str
    supplier_name: str
    supplier_code: str
    total: Optional[Decimal] = None
    freight_charges: Optional[Decimal] = None
    origin_charges: Optional[Decimal] = None
    destination_charges: Optional[Decimal] = None
    transit_time_days: Optional[int] = None
    quote_validity_date: Optional[datetime] = None
    carrier_name: Optional[str] = None
    bid_id: Optional[str] = None
    bid_created_at: Optional[datetime] = None
    is_current_user_supplier: bool = False

    model_config = ConfigDict(from_attributes=True)
