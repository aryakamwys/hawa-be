from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    return payload.get("sub")


def encrypt_user_health_data(health_data: str) -> str:
    """Encrypt health conditions data"""
    from app.core.privacy import get_privacy_protocol, DataClassification
    protocol = get_privacy_protocol()
    return protocol.encrypt_sensitive_data(health_data, DataClassification.RESTRICTED)


def decrypt_user_health_data(encrypted_data: str) -> str:
    """Decrypt health conditions data"""
    from app.core.privacy import get_privacy_protocol
    protocol = get_privacy_protocol()
    return protocol.decrypt_sensitive_data(encrypted_data)


