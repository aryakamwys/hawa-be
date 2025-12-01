from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr
    phone_e164: str | None = None
    password: str
    locale: str | None = None


class UserResponse(BaseModel):
    id: int
    full_name: str | None
    email: EmailStr
    phone_e164: str | None
    locale: str | None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


