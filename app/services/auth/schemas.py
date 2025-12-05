from pydantic import BaseModel, EmailStr, field_validator
from app.db.models.user import LanguageEnum


class RegisterRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr
    phone_e164: str | None = None
    password: str
    locale: str | None = None
    language: LanguageEnum | None = None  # Tambahkan ini


class UserResponse(BaseModel):
    id: int
    full_name: str | None
    email: EmailStr
    phone_e164: str | None
    locale: str | None
    language: str | None  # Tambahkan ini
    role: str | None = None
    
    # Personalisasi fields
    age: int | None = None
    occupation: str | None = None
    location: str | None = None
    activity_level: str | None = None
    sensitivity_level: str | None = None
    
    # Privacy
    privacy_consent: bool = False

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # "user" or "admin" - untuk menentukan redirect ke dashboard mana


class PromoteToAdminRequest(BaseModel):
    user_id: int
    admin_secret: str


class UpdateProfileRequest(BaseModel):
    """Request untuk update profile di FE
    
    Semua field optional - hanya field yang dikirim yang akan di-update
    """
    full_name: str | None = None
    phone_e164: str | None = None  # Update nomor telepon (format: +6281234567890)
    language: LanguageEnum | None = None  # Bisa diganti di profile (id, en, su)
    age: int | None = None
    occupation: str | None = None
    location: str | None = None
    activity_level: str | None = None  # sedentary, moderate, active
    sensitivity_level: str | None = None  # low, medium, high
    health_conditions: str | None = None  # Akan di-encrypt sebelum disimpan
    privacy_consent: bool | None = None
    
    @field_validator('phone_e164')
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number format (E.164)"""
        if v is not None and v != '':
            v = v.strip()
            if not v.startswith('+'):
                raise ValueError('Phone number must be in E.164 format (start with +)')
            if len(v) < 10 or len(v) > 15:
                raise ValueError('Phone number must be between 10-15 characters')
        return v
    
    @field_validator('activity_level')
    @classmethod
    def validate_activity_level(cls, v):
        """Validate activity level"""
        if v is not None and v not in ['sedentary', 'moderate', 'active']:
            raise ValueError('activity_level must be one of: sedentary, moderate, active')
        return v
    
    @field_validator('sensitivity_level')
    @classmethod
    def validate_sensitivity_level(cls, v):
        """Validate sensitivity level"""
        if v is not None and v not in ['low', 'medium', 'high']:
            raise ValueError('sensitivity_level must be one of: low, medium, high')
        return v


