"""
Transactions router — ledger queries, history, and summary.
Read-only — transactions are created by Daraja callbacks and SMS parser.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db_session
from app.models.till import Till
from app.models.transaction import (
    Transaction,
    TransactionDirection,
    TransactionStatus,
    TransactionType,
)
from app.schemas.transaction import (
    LedgerSummaryResponse,
    PaginatedTransactionsResponse,
    TransactionFilterParams,
    TransactionResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=PaginatedTransactionsResponse,
    summary="List transactions with optional filters",
)
async def list_transactions(
    till_public_id: str | None = Query(None),
    direction: TransactionDirection | None = Query(None),
    transaction_type: TransactionType | None = Query(None),
    status: TransactionStatus | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    filters = TransactionFilterParams(
        till_public_id=till_public_id,
        direction=direction,
        transaction_type=transaction_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    query = select(Transaction).where(Transaction.user_id == current_user.id)

    if filters.till_public_id:
        till_result = await db.execute(
            select(Till.id).where(
                Till.public_id == filters.till_public_id,
                Till.user_id == current_user.id,
            )
        )
        till_id = till_result.scalar_one_or_none()
        if till_id:
            query = query.where(Transaction.till_id == till_id)

    if filters.direction:
        query = query.where(Transaction.direction == filters.direction)
    if filters.transaction_type:
        query = query.where(Transaction.transaction_type == filters.transaction_type)
    if filters.status:
        query = query.where(Transaction.status == filters.status)
    if filters.date_from:
        query = query.where(Transaction.transaction_date >= filters.date_from)
    if filters.date_to:
        query = query.where(Transaction.transaction_date <= filters.date_to)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    paginated = (
        query
        .order_by(Transaction.transaction_date.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    result = await db.execute(paginated)
    transactions = result.scalars().all()

    items = []
    for txn in transactions:
        till_pub_id = None
        if txn.till_id:
            till_result = await db.execute(
                select(Till.public_id).where(Till.id == txn.till_id)
            )
            till_pub_id = till_result.scalar_one_or_none()

        items.append(TransactionResponse(
            public_id=txn.public_id,
            till_public_id=till_pub_id,
            mpesa_receipt_number=txn.mpesa_receipt_number,
            transaction_type=txn.transaction_type,
            direction=txn.direction,
            amount_kes=txn.amount_kes,
            fee_kes=txn.fee_kes,
            net_amount_kes=txn.amount_kes - txn.fee_kes,
            counterparty_name=txn.counterparty_name,
            counterparty_phone=txn.counterparty_phone,
            description=txn.description,
            status=txn.status,
            failure_reason=txn.failure_reason,
            source=txn.source,
            transaction_date=txn.transaction_date,
            created_at=txn.created_at,
        ))

    return PaginatedTransactionsResponse(
        items=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        total_pages=max(1, -(-total // filters.page_size)),
    )


@router.get(
    "/{transaction_public_id}",
    response_model=TransactionResponse,
    summary="Get a single transaction by public ID",
)
async def get_transaction(
    transaction_public_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from fastapi import HTTPException

    result = await db.execute(
        select(Transaction).where(
            Transaction.public_id == transaction_public_id,
            Transaction.user_id == current_user.id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    till_pub_id = None
    if txn.till_id:
        till_result = await db.execute(
            select(Till.public_id).where(Till.id == txn.till_id)
        )
        till_pub_id = till_result.scalar_one_or_none()

    return TransactionResponse(
        public_id=txn.public_id,
        till_public_id=till_pub_id,
        mpesa_receipt_number=txn.mpesa_receipt_number,
        transaction_type=txn.transaction_type,
        direction=txn.direction,
        amount_kes=txn.amount_kes,
        fee_kes=txn.fee_kes,
        net_amount_kes=txn.amount_kes - txn.fee_kes,
        counterparty_name=txn.counterparty_name,
        counterparty_phone=txn.counterparty_phone,
        description=txn.description,
        status=txn.status,
        failure_reason=txn.failure_reason,
        source=txn.source,
        transaction_date=txn.transaction_date,
        created_at=txn.created_at,
    )


@router.get(
    "/summary/ledger",
    response_model=LedgerSummaryResponse,
    summary="Get aggregated ledger summary for current month",
)
async def get_ledger_summary(
    period_month: str | None = Query(None, description="YYYY-MM format, defaults to current month"),
    till_public_id: str | None = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from fastapi import HTTPException

    if period_month:
        try:
            period_start = datetime.strptime(period_month, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid period_month format. Use YYYY-MM."
            )
    else:
        now = datetime.now()
        period_start = datetime(now.year, now.month, 1)

    if period_start.month == 12:
        period_end = datetime(period_start.year + 1, 1, 1)
    else:
        period_end = datetime(period_start.year, period_start.month + 1, 1)

    query = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.status == TransactionStatus.completed,
        Transaction.transaction_date >= period_start,
        Transaction.transaction_date < period_end,
    )

    if till_public_id:
        till_result = await db.execute(
            select(Till.id).where(
                Till.public_id == till_public_id,
                Till.user_id == current_user.id,
            )
        )
        till_id = till_result.scalar_one_or_none()
        if till_id:
            query = query.where(Transaction.till_id == till_id)

    result = await db.execute(query)
    transactions = result.scalars().all()

    total_credits = sum(
        t.amount_kes for t in transactions
        if t.direction == TransactionDirection.credit
    )
    total_debits = sum(
        t.amount_kes for t in transactions
        if t.direction == TransactionDirection.debit
    )
    fee_total = sum(t.fee_kes for t in transactions)

    return LedgerSummaryResponse(
        period_label=period_start.strftime("%B %Y"),
        total_credits_kes=total_credits,
        total_debits_kes=total_debits,
        net_kes=total_credits - total_debits,
        transaction_count=len(transactions),
        fee_total_kes=fee_total,
    )