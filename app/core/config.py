from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    access_token_expire_minutes: int = 60 * 24  # 1 day
    algorithm: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()


