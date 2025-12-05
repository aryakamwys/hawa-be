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
    UpdateProfileRequest,
)
from app.services.auth.service import AuthService
# Import User for profile update checks
from app.db.models.user import User


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
            language=payload.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Error in login endpoint: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {error_detail}"
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
        language=current_user.language.value if current_user.language else None,
        role=current_user.role.value,  # "user" or "admin"
        age=current_user.age,
        occupation=current_user.occupation,
        location=current_user.location,
        activity_level=current_user.activity_level,
        sensitivity_level=current_user.sensitivity_level,
        privacy_consent=current_user.privacy_consent,
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


@router.put("/profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_user_profile(
    payload: UpdateProfileRequest,
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile - user bisa edit semua field profile mereka
    
    Semua field optional - hanya field yang dikirim yang akan di-update.
    Health conditions akan di-encrypt sebelum disimpan.
    """
    from app.core.privacy import get_privacy_protocol, DataClassification
    from datetime import datetime, timezone
    
    # Update basic fields
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    
    # Update phone number (dengan validasi format E.164)
    if payload.phone_e164 is not None:
        # Check jika nomor sudah digunakan user lain
        existing_user = db.query(User).filter(
            User.phone_e164 == payload.phone_e164,
            User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered by another user"
            )
        current_user.phone_e164 = payload.phone_e164.strip() if payload.phone_e164 else None
    
    # Update language (bisa diganti di profile FE)
    if payload.language is not None:
        current_user.language = payload.language
    
    # Update personalisasi fields
    if payload.age is not None:
        current_user.age = payload.age
    if payload.occupation is not None:
        current_user.occupation = payload.occupation
    if payload.location is not None:
        current_user.location = payload.location
    if payload.activity_level is not None:
        current_user.activity_level = payload.activity_level
    if payload.sensitivity_level is not None:
        current_user.sensitivity_level = payload.sensitivity_level
    
    # Encrypt health conditions jika ada
    if payload.health_conditions is not None:
        protocol = get_privacy_protocol()
        current_user.health_conditions_encrypted = protocol.encrypt_sensitive_data(
            payload.health_conditions,
            DataClassification.RESTRICTED
        )
    
    # Update privacy consent
    if payload.privacy_consent is not None:
        current_user.privacy_consent = payload.privacy_consent
        if payload.privacy_consent:
            current_user.privacy_consent_date = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone_e164=current_user.phone_e164,
        locale=current_user.locale,
        language=current_user.language.value if current_user.language else None,
        role=current_user.role.value,
        age=current_user.age,
        occupation=current_user.occupation,
        location=current_user.location,
        activity_level=current_user.activity_level,
        sensitivity_level=current_user.sensitivity_level,
        privacy_consent=current_user.privacy_consent,
    )


