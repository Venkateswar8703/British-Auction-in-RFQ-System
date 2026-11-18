from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.enums import UserRole
from app.schemas.supplier import SupplierSimpleOut


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    supplier_id: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    supplier_id: Optional[str] = None
    supplier: Optional[SupplierSimpleOut] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


TokenResponse.model_rebuild()
