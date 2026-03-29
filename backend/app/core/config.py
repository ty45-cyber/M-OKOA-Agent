"""
Application configuration — single source of truth for all env vars.
Loaded once at startup. Never import os.environ directly elsewhere.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────
    app_name: str = "M-Okoa Agent"
    app_version: str = "1.0.0"
    environment: str = "development"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── Database ─────────────────────────────────────────
    database_url: str  # e.g. mysql+aiomysql://user:pass@host/mokoa

    # ── Redis ────────────────────────────────────────────
    redis_url: str  # e.g. redis://localhost:6379/0

    # ── Encryption key for Daraja credentials at rest ────
    field_encryption_key: str  # 32-byte base64 Fernet key

    # ── Daraja (M-Pesa) ──────────────────────────────────
    daraja_base_url: str = "https://sandbox.safaricom.co.ke"
    daraja_callback_base_url: str  # Your public HTTPS base URL

    # ── Anthropic (Claude) ───────────────────────────────
    anthropic_api_key: str

    # ── Telegram ─────────────────────────────────────────
    telegram_bot_token: str

    # ── Africa's Talking ─────────────────────────────────
    africastalking_api_key: str
    africastalking_username: str = "sandbox"
    africastalking_sender_id: str = "MOKOA"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def daraja_stk_callback_url(self) -> str:
        return f"{self.daraja_callback_base_url}/api/v1/daraja/stk-callback"

    @property
    def daraja_c2b_confirmation_url(self) -> str:
        return f"{self.daraja_callback_base_url}/api/v1/daraja/c2b-confirmation"

    @property
    def daraja_b2c_result_url(self) -> str:
        return f"{self.daraja_callback_base_url}/api/v1/daraja/b2c-result"


@lru_cache
def get_settings() -> Settings:
    """Cached settings — instantiated once per process."""
    return Settings()