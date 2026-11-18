from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User, Supplier
from app.models.enums import UserRole
from app.schemas.user import UserCreate, UserLogin, UserOut, TokenResponse
from app.services.auth import verify_password, hash_password, create_access_token
from app.services.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email.lower().strip()).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_LOGIN", "message": "Incorrect email or password"},
        )

    token_data = {"sub": user.id, "email": user.email, "role": user.role}
    if user.supplier_id:
        token_data["supplier_id"] = user.supplier_id

    access_token = create_access_token(data=token_data)
    return TokenResponse(access_token=access_token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/ws-ticket")
def create_ws_ticket(current_user: User = Depends(get_current_user)):
    """Issues a short-lived (60s) ticket for WebSocket connection auth."""
    from datetime import timedelta
    ticket_data = {
        "sub": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "ticket": True,
    }
    if current_user.supplier_id:
        ticket_data["supplier_id"] = current_user.supplier_id

    ticket = create_access_token(data=ticket_data, expires_delta=timedelta(seconds=60))
    return {"ticket": ticket, "expires_in": 60}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "An account with this email already exists"},
        )

    if user_data.role == UserRole.SUPPLIER and not user_data.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SUPPLIER_REQUIRED", "message": "Supplier accounts must specify a supplier_id"},
        )

    new_user = User(
        email=user_data.email.lower().strip(),
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role.value,
        supplier_id=user_data.supplier_id if user_data.role == UserRole.SUPPLIER else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(
        data={"sub": new_user.id, "email": new_user.email, "role": new_user.role}
    )
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(new_user))

