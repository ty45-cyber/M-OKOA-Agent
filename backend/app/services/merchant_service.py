"""
Merchant Service — automated reconciliation for Lipa na M-Pesa.

Problem it solves:
  Kamau runs a hardware shop. 50 customers pay via M-Pesa daily.
  He spends 2 hours every night matching M-Pesa SMS receipts
  to his sales book. One missed payment = lost revenue.

Solution:
  M-Okoa Agent monitors his Till via the Transaction Status API,
  auto-matches incoming C2B payments to open invoices,
  and flags unmatched payments for manual review.

Daraja APIs used:
  - C2B callback (real-time payment notification)
  - Transaction Status API (verify any suspicious or delayed payment)
  - Account Balance API (end-of-day reconciliation trigger)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.models.transaction import Transaction, TransactionStatus, TransactionDirection
from app.models.till import Till
from app.services.daraja_service import DarajaService, DarajaTillCredentials
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)


class ReconciliationResult:
    """Result of matching a payment against open invoices."""
    __slots__ = ('matched', 'invoice_ref', 'variance_kes', 'action_required')

    def __init__(
        self,
        matched: bool,
        invoice_ref: str | None = None,
        variance_kes: Decimal = Decimal('0'),
        action_required: str | None = None,
    ):
        self.matched = matched
        self.invoice_ref = invoice_ref
        self.variance_kes = variance_kes
        self.action_required = action_required


class MerchantService:
    """
    Automated reconciliation engine for Lipa na M-Pesa merchants.
    Stateless — db and daraja injected per call.
    """

    def __init__(self, db: AsyncSession, daraja: DarajaService) -> None:
        self._db = db
        self._daraja = daraja
        self._audit = AuditService(db)

    async def reconcile_payment(
        self,
        transaction: Transaction,
        open_invoices: list[dict],
    ) -> ReconciliationResult:
        """
        Attempt to match a confirmed C2B payment to an open invoice.

        Matching logic (in priority order):
        1. Exact amount match on a single open invoice
        2. Bill reference number match (customer quotes invoice number)
        3. Partial payment match (flags for review with variance)
        4. Unmatched — queued for manual reconciliation

        Args:
            transaction: The confirmed C2B credit transaction.
            open_invoices: List of dicts with keys:
                           invoice_ref, amount_kes, customer_phone, due_date

        Returns:
            ReconciliationResult with match details.
        """
        amount = transaction.amount_kes
        receipt = transaction.mpesa_receipt_number or ''
        counterparty_phone = transaction.counterparty_phone or ''

        # Priority 1: Bill reference match
        # Customer includes invoice number in the bill reference field
        for invoice in open_invoices:
            ref = invoice.get('invoice_ref', '')
            if ref and ref in (transaction.description or ''):
                variance = abs(amount - Decimal(str(invoice['amount_kes'])))
                logger.info(
                    'merchant.reconciled_by_ref',
                    receipt=receipt,
                    invoice_ref=ref,
                    variance=str(variance),
                )
                return ReconciliationResult(
                    matched=True,
                    invoice_ref=ref,
                    variance_kes=variance,
                    action_required='review_variance' if variance > Decimal('1') else None,
                )

        # Priority 2: Exact amount match
        exact_matches = [
            inv for inv in open_invoices
            if Decimal(str(inv['amount_kes'])) == amount
        ]
        if len(exact_matches) == 1:
            logger.info(
                'merchant.reconciled_by_amount',
                receipt=receipt,
                invoice_ref=exact_matches[0].get('invoice_ref'),
            )
            return ReconciliationResult(
                matched=True,
                invoice_ref=exact_matches[0].get('invoice_ref'),
                variance_kes=Decimal('0'),
            )

        # Priority 3: Phone number match
        phone_matches = [
            inv for inv in open_invoices
            if inv.get('customer_phone', '').endswith(counterparty_phone[-6:])
        ]
        if len(phone_matches) == 1:
            variance = abs(amount - Decimal(str(phone_matches[0]['amount_kes'])))
            return ReconciliationResult(
                matched=True,
                invoice_ref=phone_matches[0].get('invoice_ref'),
                variance_kes=variance,
                action_required='confirm_match' if variance > Decimal('0') else None,
            )

        # Unmatched
        logger.warning(
            'merchant.unmatched_payment',
            receipt=receipt,
            amount=str(amount),
            phone=counterparty_phone[-4:].rjust(12, '*'),
        )
        return ReconciliationResult(
            matched=False,
            action_required='manual_review',
        )

    async def verify_transaction_status(
        self,
        till: Till,
        mpesa_transaction_id: str,
        initiator_name: str,
        security_credential: str,
    ) -> dict[str, Any]:
        """
        Call the Daraja Transaction Status API to verify a payment.

        Use cases:
        - Customer claims payment was made but no C2B callback received
        - Duplicate receipt numbers in M-Pesa SMS vs callback
        - End-of-day audit of high-value transactions

        Returns raw Daraja response for the agent to interpret.
        """
        creds = DarajaTillCredentials(
            encrypted_consumer_key=till.daraja_consumer_key,
            encrypted_consumer_secret=till.daraja_consumer_secret,
            shortcode=till.daraja_shortcode,
            encrypted_passkey=till.daraja_passkey,
        )

        result = await self._daraja.query_transaction_status(
            creds=creds,
            initiator_name=initiator_name,
            security_credential=security_credential,
            transaction_id=mpesa_transaction_id,
            remarks='Merchant reconciliation check',
        )

        await self._audit.record(
            actor_type='system',
            action='merchant_transaction_verified',
            entity_type='transaction',
            payload_summary={
                'mpesa_txn_id': mpesa_transaction_id,
                'till_id': till.id,
            },
        )

        return result

    async def get_daily_reconciliation_summary(
        self,
        user_id: int,
        till_id: int,
        date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate daily collection statistics for a merchant till.

        Returns:
            total_collected_kes, transaction_count,
            matched_count, unmatched_count, fee_total_kes
        """
        target_date = date or datetime.now(timezone.utc).replace(tzinfo=None)
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=0)

        result = await self._db.execute(
            select(Transaction).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.till_id == till_id,
                    Transaction.direction == TransactionDirection.credit,
                    Transaction.status == TransactionStatus.completed,
                    Transaction.transaction_date >= day_start,
                    Transaction.transaction_date <= day_end,
                )
            )
        )
        transactions = result.scalars().all()

        total = sum(t.amount_kes for t in transactions)
        fees = sum(t.fee_kes for t in transactions)

        return {
            'date': target_date.strftime('%d %B %Y'),
            'total_collected_kes': str(total),
            'transaction_count': len(transactions),
            'fee_total_kes': str(fees),
            'net_kes': str(total - fees),
        }