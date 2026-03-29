"""
Auth Pydantic schemas — request validation and response serialization.
Input is validated and normalized before reaching the service layer.
"""
from __future__ import annotations

import re
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from app.models.user import SubscriptionTier


# ── Validators ───────────────────────────────────────────────

KENYAN_PHONE_RE = re.compile(r"^(\+254|254|0)[17]\d{8}$")
PASSWORD_MIN_LEN = 8


def normalize_kenyan_phone(raw: str) -> str:
    """Normalize to E.164 without '+': 254XXXXXXXXX"""
    phone = raw.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+254"):
        return phone[1:]
    if phone.startswith("254") and len(phone) == 12:
        return phone
    if phone.startswith("0") and len(phone) == 10:
        return f"254{phone[1:]}"
    raise ValueError(f"Invalid Kenyan phone number: {raw}")


# ── Requests ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    email: str | None = None
    password: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        if len(stripped) > 120:
            raise ValueError("Full name must not exceed 120 characters.")
        return stripped

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalize_kenyan_phone(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < PASSWORD_MIN_LEN:
            raise ValueError(f"Password must be at least {PASSWORD_MIN_LEN} characters.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        return v


class LoginRequest(BaseModel):
    phone_number: str
    password: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalize_kenyan_phone(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class BindTelegramRequest(BaseModel):
    telegram_chat_id: int


# ── Responses ────────────────────────────────────────────────

class UserPublicProfile(BaseModel):
    public_id: str
    full_name: str
    phone_number: str
    email: str | None
    subscription_tier: SubscriptionTier
    is_verified: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublicProfile