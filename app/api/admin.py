"""Admin routes - hanya bisa diakses oleh admin."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.postgres import get_db
from app.db.models.user import User, RoleEnum
from app.services.auth.schemas import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def admin_dashboard(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Dashboard admin - endpoint utama untuk admin."""
    return {
        "message": "Welcome to Admin Dashboard",
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "full_name": current_admin.full_name,
        },
        "stats": {
            "total_users": db.query(User).count(),
            "total_admins": db.query(User).filter(User.role == RoleEnum.ADMIN).count(),
        },
    }


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List semua users - hanya admin yang bisa akses."""
    users = db.query(User).all()
    return users


@router.get("/me", response_model=UserResponse)
def get_admin_info(current_admin: User = Depends(get_current_admin)):
    """Get current admin information."""
    return current_admin

