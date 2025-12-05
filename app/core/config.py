from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    admin_secret_key: str = os.getenv("ADMIN_SECRET_KEY", "change-admin-secret-in-production")
    access_token_expire_minutes: int = 60 * 24  # 1 day
    algorithm: str = "HS256"
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    google_sheets_id: str | None = os.getenv("GOOGLE_SHEETS_ID", "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA")


@lru_cache
def get_settings() -> Settings:
    return Settings()


