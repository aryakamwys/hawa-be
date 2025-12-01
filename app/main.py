from typing import Union

from dotenv import load_dotenv
from fastapi import FastAPI

from app.db.postgres import Base, engine
from app.db.models import user as user_models  # noqa: F401  # ensure model is registered
from app.api.auth import router as auth_router

# Load environment variables from .env (including DATABASE_URL)
load_dotenv()

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    """
    Initialize database schema.

    Base.metadata.create_all is idempotent: it will create tables only if they
    do not exist yet, and will not drop or modify existing ones.
    """
    Base.metadata.create_all(bind=engine)

    # Include routers
    app.include_router(auth_router)
