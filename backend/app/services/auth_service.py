"""
Auth Service — user registration, login, JWT issuance, phone verification,
Telegram chat binding.

All sensitive operations are logged to audit_log.
Passwords never appear in logs or error messages.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, SubscriptionTier
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserPublicProfile,
)
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)


class AuthError(Exception):
    """Domain error for authentication failures."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class AuthService:
    """
    Handles all identity operations.
    Stateless — db session injected per call.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    # ── Registration ─────────────────────────────────────────

    async def register(
        self,
        payload: RegisterRequest,
        ip_address: str,
    ) -> TokenResponse:
        """
        Register a new M-Okoa user.

        Rules:
        - Phone number must be unique (primary identity in Kenya)
        - Email is optional but must be unique if provided
        - Password hashed with bcrypt before storage
        """
        await self._assert_phone_not_taken(payload.phone_number)

        if payload.email:
            await self._assert_email_not_taken(payload.email)

        user = User(
            public_id=str(ULID()),
            full_name=payload.full_name.strip(),
            phone_number=payload.phone_number,
            email=payload.email.lower().strip() if payload.email else None,
            password_hash=hash_password(payload.password),
            subscription_tier=SubscriptionTier.msingi,
            is_active=True,
            is_verified=False,
        )

        self._db.add(user)
        await self._db.flush()  # Get DB-assigned id before audit log

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="user_registered",
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
            payload_summary={"phone": self._mask_phone(user.phone_number)},
        )

        logger.info(
            "auth.user_registered",
            user_id=user.id,
            phone=self._mask_phone(user.phone_number),
        )

        return self._issue_tokens(user)

    # ── Login ────────────────────────────────────────────────

    async def login(
        self,
        payload: LoginRequest,
        ip_address: str,
    ) -> TokenResponse:
        """
        Authenticate with phone number + password.
        Deliberately vague error message to prevent user enumeration (OWASP A07).
        """
        user = await self._fetch_user_by_phone(payload.phone_number)

        if not user or not verify_password(payload.password, user.password_hash):
            await self._audit.record(
                user_id=user.id if user else None,
                actor_type="user",
                action="login_failed",
                ip_address=ip_address,
                payload_summary={"phone": self._mask_phone(payload.phone_number)},
            )
            raise AuthError("Invalid credentials.", status_code=401)

        if not user.is_active:
            raise AuthError("Account is deactivated. Contact support.", status_code=403)

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="login_success",
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
            payload_summary={"phone": self._mask_phone(user.phone_number)},
        )

        logger.info(
            "auth.login_success",
            user_id=user.id,
            phone=self._mask_phone(user.phone_number),
        )

        return self._issue_tokens(user)

    # ── Token Refresh ────────────────────────────────────────

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Issue a new access token using a valid refresh token.
        Raises AuthError if token is invalid, expired, or wrong type.
        """
        from jose import JWTError

        try:
            claims = decode_token(refresh_token)
        except JWTError as exc:
            raise AuthError("Invalid or expired refresh token.", status_code=401) from exc

        if claims.get("type") != "refresh":
            raise AuthError("Token type mismatch.", status_code=401)

        user_id = int(claims["sub"])
        user = await self._fetch_user_by_id(user_id)

        if not user or not user.is_active:
            raise AuthError("User not found or deactivated.", status_code=401)

        logger.info("auth.token_refreshed", user_id=user.id)
        return self._issue_tokens(user)

    # ── Telegram Binding ─────────────────────────────────────

    async def bind_telegram_chat(
        self,
        user_id: int,
        telegram_chat_id: int,
        ip_address: str,
    ) -> None:
        """
        Associate a Telegram chat_id with a user account.
        Enables the bot to identify users from incoming messages.
        """
        existing = await self._fetch_user_by_telegram_id(telegram_chat_id)
        if existing and existing.id != user_id:
            raise AuthError(
                "This Telegram account is already linked to another M-Okoa user.",
                status_code=409,
            )

        user = await self._fetch_user_by_id(user_id)
        if not user:
            raise AuthError("User not found.", status_code=404)

        user.telegram_chat_id = telegram_chat_id

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="telegram_bound",
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
            payload_summary={"telegram_chat_id": telegram_chat_id},
        )

        logger.info("auth.telegram_bound", user_id=user.id, chat_id=telegram_chat_id)

    # ── Phone Verification ───────────────────────────────────

    async def mark_phone_verified(self, user_id: int) -> None:
        """
        Mark a user's phone number as verified.
        Called after OTP confirmation (OTP delivery via Africa's Talking SMS).
        """
        user = await self._fetch_user_by_id(user_id)
        if not user:
            raise AuthError("User not found.", status_code=404)

        user.is_verified = True
        logger.info("auth.phone_verified", user_id=user.id)

    # ── Current User (JWT dependency) ────────────────────────

    async def get_current_user(self, token: str) -> User:
        """
        Validate access token and return the authenticated user.
        Used as a FastAPI dependency via Depends().
        """
        from jose import JWTError

        try:
            claims = decode_token(token)
        except JWTError as exc:
            raise AuthError("Invalid or expired access token.", status_code=401) from exc

        if claims.get("type") != "access":
            raise AuthError("Token type mismatch.", status_code=401)

        user_id = int(claims["sub"])
        user = await self._fetch_user_by_id(user_id)

        if not user:
            raise AuthError("User not found.", status_code=401)

        if not user.is_active:
            raise AuthError("Account is deactivated.", status_code=403)

        return user

    # ── Subscription Gate ────────────────────────────────────

    @staticmethod
    def require_tier(user: User, minimum_tier: SubscriptionTier) -> None:
        """
        Enforce subscription tier access control.
        Call at the start of any tier-gated feature.

        Tier order: msingi < biashara < enterprise
        """
        tier_rank = {
            SubscriptionTier.msingi: 1,
            SubscriptionTier.biashara: 2,
            SubscriptionTier.enterprise: 3,
        }
        if tier_rank[user.subscription_tier] < tier_rank[minimum_tier]:
            raise AuthError(
                f"This feature requires the {minimum_tier.value} plan or higher.",
                status_code=403,
            )

    # ── Private helpers ──────────────────────────────────────

    def _issue_tokens(self, user: User) -> TokenResponse:
        access_token = create_access_token(user.id, user.public_id)
        refresh_token = create_refresh_token(user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserPublicProfile(
                public_id=user.public_id,
                full_name=user.full_name,
                phone_number=user.phone_number,
                email=user.email,
                subscription_tier=user.subscription_tier,
                is_verified=user.is_verified,
            ),
        )

    async def _fetch_user_by_phone(self, phone: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.phone_number == phone)
        )
        return result.scalar_one_or_none()

    async def _fetch_user_by_email(self, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def _fetch_user_by_id(self, user_id: int) -> User | None:
        result = await self._db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_user_by_telegram_id(self, chat_id: int) -> User | None:
        result = await self._db.execute(
            select(User).where(User.telegram_chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def _assert_phone_not_taken(self, phone: str) -> None:
        existing = await self._fetch_user_by_phone(phone)
        if existing:
            raise AuthError(
                "An account with this phone number already exists.",
                status_code=409,
            )

    async def _assert_email_not_taken(self, email: str) -> None:
        existing = await self._fetch_user_by_email(email)
        if existing:
            raise AuthError(
                "An account with this email address already exists.",
                status_code=409,
            )

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if len(phone) >= 8:
            return f"{phone[:4]}****{phone[-4:]}"
        return "****"