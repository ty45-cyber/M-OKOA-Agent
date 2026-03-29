"""
Transaction Pydantic schemas — request validation and response serialization.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.models.transaction import (
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)


# ── Filters ──────────────────────────────────────────────────

class TransactionFilterParams(BaseModel):
    """Query parameters for filtering the transaction ledger."""
    till_public_id: str | None = None
    direction: TransactionDirection | None = None
    transaction_type: TransactionType | None = None
    status: TransactionStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = 1
    page_size: int = 20

    @field_validator("page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Page must be 1 or greater.")
        return v

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("Page size must be between 1 and 100.")
        return v


# ── Responses ─────────────────────────────────────────────────

class TransactionResponse(BaseModel):
    public_id: str
    till_public_id: str | None = None
    mpesa_receipt_number: str | None
    transaction_type: TransactionType
    direction: TransactionDirection
    amount_kes: Decimal
    fee_kes: Decimal
    net_amount_kes: Decimal | None = None
    counterparty_name: str | None
    counterparty_phone: str | None
    description: str | None
    status: TransactionStatus
    failure_reason: str | None
    source: TransactionSource
    transaction_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class LedgerSummaryResponse(BaseModel):
    period_label: str
    total_credits_kes: Decimal
    total_debits_kes: Decimal
    net_kes: Decimal
    transaction_count: int
    fee_total_kes: Decimal


class PaginatedTransactionsResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int