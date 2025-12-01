from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Enum as SqlEnum
from sqlalchemy.sql import func
from app.db.postgres import Base


class RoleEnum(str, Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    phone_e164: Mapped[str | None] = mapped_column(String(32), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(SqlEnum(RoleEnum), default=RoleEnum.USER, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="id")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
