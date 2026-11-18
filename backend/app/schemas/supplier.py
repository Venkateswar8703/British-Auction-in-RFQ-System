from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime


class SupplierSimpleOut(BaseModel):
    id: str
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)


class SupplierBase(BaseModel):
    name: str
    code: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierOut(SupplierBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
