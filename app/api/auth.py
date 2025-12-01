from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.services.auth.schemas import (
    RegisterRequest,
    UserResponse,
    LoginRequest,
    TokenResponse,
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
    return TokenResponse(access_token=token)


