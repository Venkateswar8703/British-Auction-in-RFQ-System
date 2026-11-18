from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import Supplier, User
from app.schemas.supplier import SupplierOut
from app.services.deps import require_buyer

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", response_model=List[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_buyer),
):
    suppliers = db.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name.asc()).all()
    return [SupplierOut.model_validate(s) for s in suppliers]

