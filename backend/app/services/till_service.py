"""
Till Service — onboarding, credential management, balance queries,
Smart Float rule evaluation, and C2B URL registration.

Daraja credentials are encrypted before storage and decrypted only
at call time inside DarajaTillCredentials. They never appear in logs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.security import encrypt_field
from app.models.till import Till, TillType
from app.models.user import User, SubscriptionTier
from app.schemas.till import (
    TillCreateRequest,
    TillResponse,
    TillUpdateRequest,
    BalanceResponse,
    SmartFloatRuleRequest,
    SmartFloatRuleResponse,
)
from app.models.smart_float_rule import SmartFloatRule, DestinationType
from app.services.audit_service import AuditService
from app.services.daraja_service import (
    DarajaError,
    DarajaService,
    DarajaTillCredentials,
)
from app.core.redis_client import RedisKeys, get_redis
from app.services.auth_service import AuthError

logger = structlog.get_logger(__name__)

# Tier limits on number of tills
TILL_LIMITS: dict[SubscriptionTier, int] = {
    SubscriptionTier.msingi: 1,
    SubscriptionTier.biashara: 5,
    SubscriptionTier.enterprise: 999,
}

# Balance cache TTL in seconds (5 minutes)
BALANCE_CACHE_TTL = 300


class TillError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class TillService:
    """
    All operations on M-Pesa Till and Paybill accounts.
    Stateless — db and daraja service injected per call.
    """

    def __init__(self, db: AsyncSession, daraja: DarajaService) -> None:
        self._db = db
        self._daraja = daraja
        self._audit = AuditService(db)

    # ── Onboard a new Till ───────────────────────────────────

    async def add_till(
        self,
        user: User,
        payload: TillCreateRequest,
        ip_address: str,
    ) -> TillResponse:
        """
        Register a new M-Pesa Till or Paybill for a user.

        Steps:
        1. Enforce subscription tier till limit
        2. Prevent duplicate till numbers per user
        3. Encrypt Daraja credentials before storage
        4. Persist till
        5. Register C2B callback URLs with Safaricom (if credentials provided)
        6. Write audit entry
        """
        await self._enforce_till_limit(user)
        await self._assert_till_not_duplicate(user.id, payload.till_number)

        encrypted_key = encrypt_field(payload.daraja_consumer_key) if payload.daraja_consumer_key else None
        encrypted_secret = encrypt_field(payload.daraja_consumer_secret) if payload.daraja_consumer_secret else None
        encrypted_passkey = encrypt_field(payload.daraja_passkey) if payload.daraja_passkey else None

        till = Till(
            public_id=str(ULID()),
            user_id=user.id,
            display_name=payload.display_name.strip(),
            till_number=payload.till_number.strip(),
            till_type=payload.till_type,
            is_active=True,
            daraja_consumer_key=encrypted_key,
            daraja_consumer_secret=encrypted_secret,
            daraja_shortcode=payload.daraja_shortcode,
            daraja_passkey=encrypted_passkey,
            float_threshold_kes=payload.float_threshold_kes,
            float_target_account=payload.float_target_account,
        )

        self._db.add(till)
        await self._db.flush()

        # Register C2B URLs if full Daraja credentials are provided
        if self._has_full_daraja_credentials(till):
            await self._register_c2b_urls_safe(till)

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="till_added",
            entity_type="till",
            entity_id=till.id,
            ip_address=ip_address,
            payload_summary={
                "till_number": till.till_number,
                "till_type": till.till_type.value,
                "display_name": till.display_name,
            },
        )

        logger.info(
            "till.added",
            user_id=user.id,
            till_id=till.id,
            till_number=till.till_number,
        )

        return TillResponse.model_validate(till)

    # ── Fetch user's tills ───────────────────────────────────

    async def list_tills(self, user_id: int) -> list[TillResponse]:
        """Return all active tills for a user."""
        result = await self._db.execute(
            select(Till)
            .where(Till.user_id == user_id, Till.is_active == True)
            .order_by(Till.created_at.asc())
        )
        tills = result.scalars().all()
        return [TillResponse.model_validate(t) for t in tills]

    async def get_till(self, user_id: int, till_public_id: str) -> Till:
        """
        Fetch a single till belonging to the user.
        Raises TillError if not found or not owned by user.
        """
        result = await self._db.execute(
            select(Till).where(
                Till.public_id == till_public_id,
                Till.user_id == user_id,
                Till.is_active == True,
            )
        )
        till = result.scalar_one_or_none()
        if not till:
            raise TillError("Till not found.", status_code=404)
        return till

    # ── Update Till ──────────────────────────────────────────

    async def update_till(
        self,
        user: User,
        till_public_id: str,
        payload: TillUpdateRequest,
        ip_address: str,
    ) -> TillResponse:
        """
        Update till display name, float config, or Daraja credentials.
        Re-encrypts credentials if new values are provided.
        Re-registers C2B URLs if shortcode changes.
        """
        till = await self.get_till(user.id, till_public_id)

        if payload.display_name is not None:
            till.display_name = payload.display_name.strip()

        if payload.float_threshold_kes is not None:
            till.float_threshold_kes = payload.float_threshold_kes

        if payload.float_target_account is not None:
            till.float_target_account = payload.float_target_account.strip()

        shortcode_changed = False
        if payload.daraja_consumer_key is not None:
            till.daraja_consumer_key = encrypt_field(payload.daraja_consumer_key)
        if payload.daraja_consumer_secret is not None:
            till.daraja_consumer_secret = encrypt_field(payload.daraja_consumer_secret)
        if payload.daraja_passkey is not None:
            till.daraja_passkey = encrypt_field(payload.daraja_passkey)
        if payload.daraja_shortcode is not None:
            shortcode_changed = payload.daraja_shortcode != till.daraja_shortcode
            till.daraja_shortcode = payload.daraja_shortcode

        await self._db.flush()

        if shortcode_changed and self._has_full_daraja_credentials(till):
            await self._register_c2b_urls_safe(till)

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="till_updated",
            entity_type="till",
            entity_id=till.id,
            ip_address=ip_address,
            payload_summary={"till_public_id": till_public_id},
        )

        return TillResponse.model_validate(till)

    # ── Deactivate Till ──────────────────────────────────────

    async def deactivate_till(
        self,
        user: User,
        till_public_id: str,
        ip_address: str,
    ) -> None:
        """Soft-delete a till. Transactions are preserved."""
        till = await self.get_till(user.id, till_public_id)
        till.is_active = False

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="till_deactivated",
            entity_type="till",
            entity_id=till.id,
            ip_address=ip_address,
            payload_summary={"till_number": till.till_number},
        )

        logger.info("till.deactivated", till_id=till.id, user_id=user.id)

    # ── Balance Query ────────────────────────────────────────

    async def query_balance(
        self,
        user: User,
        till_public_id: str,
        force_refresh: bool = False,
    ) -> BalanceResponse:
        """
        Return the current balance for a till.

        Strategy:
        1. If cached in Redis and not force_refresh → return cache
        2. If till has full Daraja credentials → query Daraja (async, sets callback)
        3. Fall back to last_known_balance from DB if Daraja unavailable
        """
        till = await self.get_till(user.id, till_public_id)
        redis = get_redis()
        cache_key = RedisKeys.till_balance_cache(till.id)

        if not force_refresh:
            cached = await redis.get(cache_key)
            if cached:
                logger.info("till.balance_cache_hit", till_id=till.id)
                return BalanceResponse(
                    till_public_id=till.public_id,
                    display_name=till.display_name,
                    balance_kes=Decimal(cached),
                    source="cache",
                    updated_at=till.balance_updated_at,
                )

        if not self._has_full_daraja_credentials(till):
            if till.last_known_balance_kes is not None:
                return BalanceResponse(
                    till_public_id=till.public_id,
                    display_name=till.display_name,
                    balance_kes=till.last_known_balance_kes,
                    source="last_known",
                    updated_at=till.balance_updated_at,
                )
            raise TillError(
                "Daraja credentials not configured for this till. "
                "Please add your M-Pesa API credentials.",
                status_code=422,
            )

        # Daraja balance query is async (callback-based).
        # We initiate it here and return last known in the meantime.
        # The balance-result callback will update the DB and cache.
        creds = self._build_credentials(till)
        try:
            await self._daraja.query_account_balance(
                creds=creds,
                initiator_name="MokoaAgent",
                security_credential="",  # Set at Daraja go-live
                remarks=f"Balance query for {till.display_name}",
            )
        except DarajaError as exc:
            logger.warning(
                "till.balance_query_failed",
                till_id=till.id,
                error=str(exc),
            )

        return BalanceResponse(
            till_public_id=till.public_id,
            display_name=till.display_name,
            balance_kes=till.last_known_balance_kes or Decimal("0.00"),
            source="last_known",
            updated_at=till.balance_updated_at,
        )

    async def update_cached_balance(
        self,
        till_id: int,
        balance_kes: Decimal,
    ) -> None:
        """
        Called by the Daraja balance-result callback handler.
        Updates DB and Redis cache atomically.
        """
        result = await self._db.execute(
            select(Till).where(Till.id == till_id)
        )
        till = result.scalar_one_or_none()
        if not till:
            logger.warning("till.balance_update_missing", till_id=till_id)
            return

        till.last_known_balance_kes = balance_kes
        till.balance_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.flush()

        redis = get_redis()
        await redis.setex(
            RedisKeys.till_balance_cache(till.id),
            BALANCE_CACHE_TTL,
            str(balance_kes),
        )

        logger.info(
            "till.balance_updated",
            till_id=till_id,
            balance_kes=str(balance_kes),
        )

    # ── Aggregate balance across all tills ───────────────────

    async def aggregate_all_balances(self, user: User) -> list[BalanceResponse]:
        """
        Return balance for every active till owned by the user.
        Used by the agent to answer: "Uko na pesa ngapi kwa till zote?"
        """
        result = await self._db.execute(
            select(Till).where(
                Till.user_id == user.id,
                Till.is_active == True,
            )
        )
        tills = result.scalars().all()
        balances: list[BalanceResponse] = []

        for till in tills:
            redis = get_redis()
            cached = await redis.get(RedisKeys.till_balance_cache(till.id))
            balance = (
                Decimal(cached)
                if cached
                else (till.last_known_balance_kes or Decimal("0.00"))
            )
            balances.append(
                BalanceResponse(
                    till_public_id=till.public_id,
                    display_name=till.display_name,
                    balance_kes=balance,
                    source="cache" if cached else "last_known",
                    updated_at=till.balance_updated_at,
                )
            )

        return balances

    # ── Smart Float Rules ────────────────────────────────────

    async def add_smart_float_rule(
        self,
        user: User,
        till_public_id: str,
        payload: SmartFloatRuleRequest,
        ip_address: str,
    ) -> SmartFloatRuleResponse:
        """
        Create an automation rule on a till.
        "If balance > threshold, move amount to destination."
        """
        till = await self.get_till(user.id, till_public_id)

        rule = SmartFloatRule(
            public_id=str(ULID()),
            user_id=user.id,
            till_id=till.id,
            rule_name=payload.rule_name.strip(),
            trigger_threshold_kes=payload.trigger_threshold_kes,
            transfer_amount_kes=payload.transfer_amount_kes,
            destination_type=payload.destination_type,
            destination_ref=payload.destination_ref.strip(),
            destination_name=payload.destination_name,
            is_active=True,
        )

        self._db.add(rule)
        await self._db.flush()

        await self._audit.record(
            user_id=user.id,
            actor_type="user",
            action="smart_float_rule_created",
            entity_type="smart_float_rule",
            entity_id=rule.id,
            ip_address=ip_address,
            payload_summary={
                "rule_name": rule.rule_name,
                "threshold": str(rule.trigger_threshold_kes),
                "destination_type": rule.destination_type.value,
            },
        )

        return SmartFloatRuleResponse.model_validate(rule)

    async def evaluate_smart_float_rules(
        self,
        till: Till,
        current_balance: Decimal,
    ) -> list[SmartFloatRule]:
        """
        Return all active rules on this till that the current balance triggers.
        Called by the Daraja balance callback after every balance update.
        """
        result = await self._db.execute(
            select(SmartFloatRule).where(
                SmartFloatRule.till_id == till.id,
                SmartFloatRule.is_active == True,
                SmartFloatRule.trigger_threshold_kes <= current_balance,
            )
        )
        triggered = result.scalars().all()

        if triggered:
            logger.info(
                "till.smart_float_rules_triggered",
                till_id=till.id,
                count=len(triggered),
                balance=str(current_balance),
            )

        return list(triggered)

    # ── Private helpers ──────────────────────────────────────

    async def _enforce_till_limit(self, user: User) -> None:
        result = await self._db.execute(
            select(Till).where(
                Till.user_id == user.id,
                Till.is_active == True,
            )
        )
        count = len(result.scalars().all())
        limit = TILL_LIMITS[user.subscription_tier]

        if count >= limit:
            raise TillError(
                f"Your {user.subscription_tier.value} plan allows up to {limit} till(s). "
                f"Upgrade to add more.",
                status_code=403,
            )

    async def _assert_till_not_duplicate(self, user_id: int, till_number: str) -> None:
        result = await self._db.execute(
            select(Till).where(
                Till.user_id == user_id,
                Till.till_number == till_number,
                Till.is_active == True,
            )
        )
        if result.scalar_one_or_none():
            raise TillError(
                f"Till number {till_number} is already registered on your account.",
                status_code=409,
            )

    async def _register_c2b_urls_safe(self, till: Till) -> None:
        """Register C2B URLs — failure is non-fatal, logged as warning."""
        try:
            creds = self._build_credentials(till)
            await self._daraja.register_c2b_urls(creds)
            logger.info("till.c2b_urls_registered", till_id=till.id)
        except DarajaError as exc:
            logger.warning(
                "till.c2b_registration_failed",
                till_id=till.id,
                error=str(exc),
            )

    @staticmethod
    def _has_full_daraja_credentials(till: Till) -> bool:
        return all([
            till.daraja_consumer_key,
            till.daraja_consumer_secret,
            till.daraja_shortcode,
            till.daraja_passkey,
        ])

    @staticmethod
    def _build_credentials(till: Till) -> DarajaTillCredentials:
        return DarajaTillCredentials(
            encrypted_consumer_key=till.daraja_consumer_key,
            encrypted_consumer_secret=till.daraja_consumer_secret,
            shortcode=till.daraja_shortcode,
            encrypted_passkey=till.daraja_passkey,
        )