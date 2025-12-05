from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token
from app.db.models.user import User, RoleEnum, LanguageEnum


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register_user(
        self,
        *,
        full_name: str | None,
        email: str,
        phone_e164: str | None,
        password: str,
        locale: str | None = None,
        language: LanguageEnum | None = None,
    ) -> User:
        # check existing email / phone
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("Email already registered")
        if phone_e164 and self.db.query(User).filter(User.phone_e164 == phone_e164).first():
            raise ValueError("Phone number already registered")

        user = User(
            full_name=full_name,
            email=email,
            phone_e164=phone_e164,
            password_hash=hash_password(password),
        )
        if locale:
            user.locale = locale
        if language:
            user.language = language
        else:
            user.language = LanguageEnum.ID  # Default

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, *, email: str, password: str) -> str | None:
        user = self.db.query(User).filter(User.email == email).first()
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return create_access_token(str(user.id))

    def promote_to_admin(self, *, user_id: int) -> User:
        """Promote a user to admin role."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise ValueError("User not found")
        user.role = RoleEnum.ADMIN
        self.db.commit()
        self.db.refresh(user)
        return user


