"""
Tax Service — automatic KRA compliance.
Locks DST (1.5%) and VAT (16%) from every M-Pesa inflow into a virtual sub-wallet.
The user cannot accidentally spend locked tax funds.

Tax types:
  DST  = Digital Services Tax, 1.5% on digital service inflows
  VAT  = Value Added Tax, 16% (applies to VAT-registered businesses)

By default we lock DST for all users and skip VAT unless the user
is VAT-registered (enterprise tier).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.models.tax_lock import TaxLock, TaxLockStatus, TaxType
from app.models.transaction import Transaction, TransactionDirection
from app.models.user import User, SubscriptionTier

logger = structlog.get_logger(__name__)

# KRA rates
DST_RATE = Decimal("0.0150")   # 1.5% Digital Services Tax
VAT_RATE = Decimal("0.1600")   # 16% VAT (enterprise tier only)


class TaxService:
    """
    Calculates and locks tax obligations from inflows.
    Stateless — db session injected per call.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def lock_tax_on_inflow(
        self,
        user_id: int,
        till_id: int,
        transaction: Transaction,
    ) -> list[TaxLock]:
        """
        Called immediately after every confirmed credit transaction.
        Calculates applicable taxes and creates lock records.

        Returns list of created TaxLock records (may be empty if amount too small).
        """
        if transaction.direction != TransactionDirection.credit:
            return []

        if transaction.amount_kes <= Decimal("0"):
            return []

        user = await self._fetch_user(user_id)
        if not user:
            logger.warning("tax.user_not_found", user_id=user_id)
            return []

        period = self._current_period()
        created_locks: list[TaxLock] = []

        # DST applies to all tiers
        dst_lock = await self._create_lock(
            user_id=user_id,
            till_id=till_id,
            tax_type=TaxType.dst,
            taxable_amount=transaction.amount_kes,
            rate=DST_RATE,
            period=period,
        )
        if dst_lock:
            created_locks.append(dst_lock)

        # VAT only for enterprise-tier (VAT-registered businesses)
        if user.subscription_tier == SubscriptionTier.enterprise:
            vat_lock = await self._create_lock(
                user_id=user_id,
                till_id=till_id,
                tax_type=TaxType.vat,
                taxable_amount=transaction.amount_kes,
                rate=VAT_RATE,
                period=period,
            )
            if vat_lock:
                created_locks.append(vat_lock)

        if created_locks:
            total_locked = sum(lock.locked_amount_kes for lock in created_locks)
            logger.info(
                "tax.locked",
                user_id=user_id,
                till_id=till_id,
                transaction_id=transaction.id,
                total_locked=str(total_locked),
                period=period,
            )

        return created_locks

    async def get_tax_summary(
        self,
        user_id: int,
        period_month: str | None = None,
    ) -> dict:
        """
        Return total locked tax amounts per type for a user.
        If period_month is None, returns current month.

        Used by the agent to answer: "Ninaeza toa pesa ngapi bila kuingia shida na KRA?"
        """
        period = period_month or self._current_period()

        result = await self._db.execute(
            select(
                TaxLock.tax_type,
                func.sum(TaxLock.locked_amount_kes).label("total_locked"),
            )
            .where(
                TaxLock.user_id == user_id,
                TaxLock.period_month == period,
                TaxLock.status == TaxLockStatus.locked,
            )
            .group_by(TaxLock.tax_type)
        )
        rows = result.all()

        breakdown = {row.tax_type.value: Decimal(str(row.total_locked)) for row in rows}
        total = sum(breakdown.values())

        return {
            "period_month": period,
            "breakdown": breakdown,
            "total_locked_kes": total,
        }

    async def get_available_balance(
        self,
        user_id: int,
        till_id: int,
        gross_balance: Decimal,
    ) -> Decimal:
        """
        Return spendable balance after subtracting locked tax.
        gross_balance - total_locked_this_period = available

        This is the number the agent presents to the user — not the raw M-Pesa balance.
        """
        period = self._current_period()

        result = await self._db.execute(
            select(func.sum(TaxLock.locked_amount_kes))
            .where(
                TaxLock.user_id == user_id,
                TaxLock.till_id == till_id,
                TaxLock.period_month == period,
                TaxLock.status == TaxLockStatus.locked,
            )
        )
        total_locked = result.scalar_one_or_none() or Decimal("0.00")
        available = gross_balance - Decimal(str(total_locked))
        return max(available, Decimal("0.00"))

    # ── Private helpers ──────────────────────────────────────

    async def _create_lock(
        self,
        user_id: int,
        till_id: int,
        tax_type: TaxType,
        taxable_amount: Decimal,
        rate: Decimal,
        period: str,
    ) -> TaxLock | None:
        locked_amount = (taxable_amount * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Don't create trivially small locks (< 1 KES)
        if locked_amount < Decimal("1.00"):
            return None

        lock = TaxLock(
            public_id=str(ULID()),
            user_id=user_id,
            till_id=till_id,
            tax_type=tax_type,
            taxable_amount_kes=taxable_amount,
            tax_rate=rate,
            locked_amount_kes=locked_amount,
            period_month=period,
            status=TaxLockStatus.locked,
        )
        self._db.add(lock)
        await self._db.flush()
        return lock

    async def _fetch_user(self, user_id: int) -> User | None:
        from sqlalchemy import select as sa_select
        result = await self._db.execute(
            sa_select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _current_period() -> str:
        """Returns current period as YYYY-MM string."""
        return datetime.now(timezone.utc).strftime("%Y-%m")
