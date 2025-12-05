from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Enum as SqlEnum, Text, Boolean
from sqlalchemy.sql import func
from app.db.postgres import Base


class RoleEnum(str, Enum):
    USER = "user"
    ADMIN = "admin"


class LanguageEnum(str, Enum):
    """3 bahasa yang didukung"""
    ID = "id"  # Bahasa Indonesia
    EN = "en"  # English
    SU = "su"  # Bahasa Sunda


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    phone_e164: Mapped[str | None] = mapped_column(String(32), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(SqlEnum(RoleEnum), default=RoleEnum.USER, nullable=False)
    
    # Language preference (bisa diganti di profile)
    language: Mapped[LanguageEnum] = mapped_column(
        SqlEnum(LanguageEnum), 
        default=LanguageEnum.ID, 
        nullable=False
    )
    locale: Mapped[str] = mapped_column(String(8), default="id")  # Keep for backward compatibility
    
    # Personalisasi fields untuk rekomendasi cuaca
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Kota/Kabupaten di Jawa Barat
    activity_level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # sedentary, moderate, active
    sensitivity_level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # low, medium, high
    
    # Health conditions (encrypted - sensitive data)
    health_conditions_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Privacy consent
    privacy_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    privacy_consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
