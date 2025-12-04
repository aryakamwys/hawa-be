from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.db.postgres import get_db

if TYPE_CHECKING:
    from app.db.models.user import User
from app.services.auth.schemas import (
    RegisterRequest,
    UserResponse,
    LoginRequest,
    TokenResponse,
    PromoteToAdminRequest,
)
from app.services.auth.service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user = service.register_user(
            full_name=payload.full_name,
            email=payload.email,
            phone_e164=payload.phone_e164,
            password=payload.password,
            locale=payload.locale,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    token = service.authenticate_user(email=payload.email, password=payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # Get user to include role in response
    from app.db.models.user import User
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    return TokenResponse(
        access_token=token,
        role=user.role.value  # "user" or "admin"
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: "User" = Depends(get_current_user)):
    """Get current authenticated user information including role.
    
    Frontend bisa gunakan endpoint ini untuk:
    1. Verify token masih valid
    2. Get user info termasuk role untuk redirect ke dashboard yang sesuai
    """
    return UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone_e164=current_user.phone_e164,
        locale=current_user.locale,
        role=current_user.role.value,  # "user" or "admin"
    )


@router.post("/promote-admin", response_model=UserResponse)
def promote_to_admin(payload: PromoteToAdminRequest, db: Session = Depends(get_db)):
    """Promote a user to admin role. Requires ADMIN_SECRET_KEY."""
    settings = get_settings()
    if payload.admin_secret != settings.admin_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret key",
        )
    service = AuthService(db)
    try:
        user = service.promote_to_admin(user_id=payload.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return user


