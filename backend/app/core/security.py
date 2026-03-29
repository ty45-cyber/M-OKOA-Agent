"""
Security utilities — JWT, password hashing, field-level encryption for Daraja credentials.
OWASP A02: Cryptographic Failures — all sensitive fields encrypted before DB storage.
"""
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext
import base64
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.field_encryption_key.encode()
        _fernet = Fernet(key)
    return _fernet


# ── Password ─────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────

def create_access_token(user_id: int, public_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "pid": public_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    """Raises JWTError on invalid or expired tokens."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# ── Field-level encryption (Daraja credentials) ──────────────

def encrypt_field(plaintext: str) -> str:
    """Encrypt a sensitive string before DB storage."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a DB-stored encrypted field."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()