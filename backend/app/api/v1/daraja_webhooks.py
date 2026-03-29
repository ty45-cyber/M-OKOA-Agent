"""
Daraja Webhook Handlers — the entry point for all M-Pesa callbacks.

Safaricom calls these URLs asynchronously after every transaction event.
Rules:
- Every handler must respond HTTP 200 within 5 seconds or Safaricom retries.
- All payloads are deduplicated via idempotency_key before processing.
- Raw payload is always stored before any business logic runs.
- Agent sessions awaiting a callback are resumed here.
- Every event is written to the audit log.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.redis_client import RedisKeys, get_redis
from app.models.agent_session import AgentSession, SessionStatus
from app.models.till import Till
from app.models.transaction import (
    Transaction,
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)
from app.services.audit_service import AuditService
from app.services.tax_service import TaxService
from app.services.till_service import TillService
from app.services.daraja_service import get_daraja_service
from ulid import ULID

logger = structlog.get_logger(__name__)
router = APIRouter()

# Safaricom expects exactly this response on successful C2B validation
C2B_ACCEPT_RESPONSE = {"ResultCode": 0, "ResultDesc": "Accepted"}
C2B_REJECT_RESPONSE = {"ResultCode": 1, "ResultDesc": "Rejected"}


# ── Helpers ───────────────────────────────────────────────────

def _daraja_ok() -> JSONResponse:
    """Standard Daraja success acknowledgement — must return in < 5 seconds."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"ResultCode": 0, "ResultDesc": "Success"},
    )


def _build_idempotency_key(source: str, reference: str) -> str:
    """Deterministic key to prevent double-processing of retried callbacks."""
    raw = f"{source}:{reference}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _is_duplicate(db: AsyncSession, idempotency_key: str) -> bool:
    result = await db.execute(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    )
    return result.scalar_one_or_none() is not None


async def _fetch_till_by_shortcode(
    db: AsyncSession, shortcode: str
) -> Till | None:
    result = await db.execute(
        select(Till).where(
            Till.daraja_shortcode == shortcode,
            Till.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def _resume_agent_session(
    db: AsyncSession,
    checkout_request_id: str,
    transaction: Transaction,
) -> None:
    """
    Resume a LangGraph agent session that was paused waiting for this callback.
    The agent picks up from the 'awaiting_callback' node with the transaction result.
    """
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.stk_correlation_id == checkout_request_id,
            AgentSession.status == SessionStatus.awaiting_callback,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return

    # Update the graph state with the confirmed transaction
    state: dict = session.graph_state or {}
    state["confirmed_transaction_id"] = transaction.public_id
    state["confirmed_amount"] = str(transaction.amount_kes)
    state["transaction_status"] = transaction.status.value

    session.graph_state = state
    session.current_node = "post_payment_response"
    session.status = SessionStatus.active

    # Notify the agent runner via Redis pub/sub so it can continue
    redis = get_redis()
    await redis.publish(
        f"agent:resume:{session.public_id}",
        transaction.public_id,
    )

    logger.info(
        "agent.session_resumed",
        session_id=session.public_id,
        transaction_id=transaction.public_id,
    )


# ── STK Push Callback ─────────────────────────────────────────

@router.post(
    "/stk-callback",
    summary="Receive STK Push payment result from Safaricom",
    include_in_schema=False,  # Not exposed in public docs
)
async def stk_push_callback(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Safaricom calls this after the customer completes or cancels the STK PIN prompt.

    Success payload contains: MpesaReceiptNumber, Amount, PhoneNumber, TransactionDate.
    Failure payload contains: ResultCode (non-zero), ResultDesc.
    """
    raw_body: dict = await request.json()
    audit = AuditService(db)

    try:
        callback = raw_body["Body"]["stkCallback"]
        checkout_request_id: str = callback["CheckoutRequestID"]
        merchant_request_id: str = callback["MerchantRequestID"]
        result_code: int = callback["ResultCode"]
        result_desc: str = callback["ResultDesc"]

        idempotency_key = _build_idempotency_key("stk", checkout_request_id)

        if await _is_duplicate(db, idempotency_key):
            logger.info("daraja.stk_callback_duplicate", checkout_id=checkout_request_id)
            return _daraja_ok()

        # Retrieve the pending STK session from Redis
        redis = get_redis()
        session_data_raw = await redis.get(RedisKeys.stk_session(checkout_request_id))

        if not session_data_raw:
            logger.warning(
                "daraja.stk_callback_no_session",
                checkout_id=checkout_request_id,
            )
            return _daraja_ok()

        import json
        session_data: dict = json.loads(session_data_raw)
        till_id: int = session_data["till_id"]
        user_id: int = session_data["user_id"]

        # Fetch the till
        till_result = await db.execute(select(Till).where(Till.id == till_id))
        till = till_result.scalar_one_or_none()
        if not till:
            logger.error("daraja.stk_callback_till_missing", till_id=till_id)
            return _daraja_ok()

        if result_code == 0:
            # Payment completed successfully
            items: list[dict] = callback.get("CallbackMetadata", {}).get("Item", [])
            meta = {item["Name"]: item.get("Value") for item in items}

            receipt_number: str = str(meta.get("MpesaReceiptNumber", ""))
            amount_kes = Decimal(str(meta.get("Amount", "0")))
            phone_number: str = str(meta.get("PhoneNumber", ""))
            raw_txn_date: str = str(meta.get("TransactionDate", ""))

            try:
                txn_date = datetime.strptime(raw_txn_date, "%Y%m%d%H%M%S")
            except ValueError:
                txn_date = datetime.now(timezone.utc).replace(tzinfo=None)

            transaction = Transaction(
                public_id=str(ULID()),
                user_id=user_id,
                till_id=till_id,
                mpesa_receipt_number=receipt_number,
                mpesa_transaction_id=checkout_request_id,
                transaction_type=TransactionType.stk_push,
                direction=TransactionDirection.credit,
                amount_kes=amount_kes,
                fee_kes=Decimal("0.00"),
                counterparty_phone=phone_number,
                description=session_data.get("description", "STK Push payment"),
                status=TransactionStatus.completed,
                source=TransactionSource.daraja_callback,
                raw_payload=raw_body,
                idempotency_key=idempotency_key,
                transaction_date=txn_date,
            )
            db.add(transaction)
            await db.flush()

            # Lock tax portion for KRA compliance
            tax_service = TaxService(db)
            await tax_service.lock_tax_on_inflow(
                user_id=user_id,
                till_id=till_id,
                transaction=transaction,
            )

            # Resume agent session if waiting on this payment
            await _resume_agent_session(db, checkout_request_id, transaction)

            # Clean up the Redis STK session
            await redis.delete(RedisKeys.stk_session(checkout_request_id))

            await audit.record(
                user_id=user_id,
                actor_type="daraja_callback",
                action="stk_push_completed",
                entity_type="transaction",
                entity_id=transaction.id,
                payload_summary={
                    "receipt": receipt_number,
                    "amount": str(amount_kes),
                    "phone": phone_number[-4:].rjust(12, "*"),
                },
            )

            logger.info(
                "daraja.stk_push_completed",
                receipt=receipt_number,
                amount=str(amount_kes),
                till_id=till_id,
            )

        else:
            # Payment failed or was cancelled by user
            transaction = Transaction(
                public_id=str(ULID()),
                user_id=user_id,
                till_id=till_id,
                mpesa_transaction_id=checkout_request_id,
                transaction_type=TransactionType.stk_push,
                direction=TransactionDirection.credit,
                amount_kes=Decimal(str(session_data.get("amount", "0"))),
                fee_kes=Decimal("0.00"),
                description=session_data.get("description", "STK Push payment"),
                status=TransactionStatus.failed,
                failure_reason=result_desc,
                source=TransactionSource.daraja_callback,
                raw_payload=raw_body,
                idempotency_key=idempotency_key,
                transaction_date=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(transaction)
            await db.flush()

            await _resume_agent_session(db, checkout_request_id, transaction)
            await redis.delete(RedisKeys.stk_session(checkout_request_id))

            await audit.record(
                user_id=user_id,
                actor_type="daraja_callback",
                action="stk_push_failed",
                entity_type="transaction",
                entity_id=transaction.id,
                payload_summary={
                    "result_code": result_code,
                    "reason": result_desc,
                },
            )

            logger.info(
                "daraja.stk_push_failed",
                result_code=result_code,
                reason=result_desc,
                till_id=till_id,
            )

    except Exception as exc:
        logger.error(
            "daraja.stk_callback_error",
            error=str(exc),
            body=str(raw_body)[:500],
        )

    return _daraja_ok()


# ── C2B Validation ────────────────────────────────────────────

@router.post(
    "/c2b-validation",
    summary="Validate incoming C2B payment before it is accepted",
    include_in_schema=False,
)
async def c2b_validation(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Called by Safaricom BEFORE debiting the customer.
    Return ResultCode 0 to accept, 1 to reject.

    We accept all valid payments — rejection is reserved for
    blocked accounts or amounts outside business rules.
    """
    raw_body: dict = await request.json()

    try:
        shortcode: str = str(raw_body.get("BusinessShortCode", ""))
        till = await _fetch_till_by_shortcode(db, shortcode)

        if not till:
            logger.warning(
                "daraja.c2b_validation_unknown_shortcode",
                shortcode=shortcode,
            )
            return JSONResponse(content=C2B_REJECT_RESPONSE)

        if not till.is_active:
            return JSONResponse(content=C2B_REJECT_RESPONSE)

        logger.info(
            "daraja.c2b_validated",
            shortcode=shortcode,
            till_id=till.id,
        )
        return JSONResponse(content=C2B_ACCEPT_RESPONSE)

    except Exception as exc:
        logger.error("daraja.c2b_validation_error", error=str(exc))
        # Accept on error — do not block legitimate payments
        return JSONResponse(content=C2B_ACCEPT_RESPONSE)


# ── C2B Confirmation ──────────────────────────────────────────

@router.post(
    "/c2b-confirmation",
    summary="Receive confirmed C2B payment from Safaricom",
    include_in_schema=False,
)
async def c2b_confirmation(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Called by Safaricom after the customer's M-Pesa is successfully debited.
    This is the authoritative confirmation — money has moved.
    """
    raw_body: dict = await request.json()
    audit = AuditService(db)

    try:
        transaction_type: str = raw_body.get("TransactionType", "")
        transaction_id: str = raw_body.get("TransID", "")
        trans_time: str = raw_body.get("TransTime", "")
        amount_str: str = str(raw_body.get("TransAmount", "0"))
        shortcode: str = str(raw_body.get("BusinessShortCode", ""))
        bill_ref: str = raw_body.get("BillRefNumber", "")
        msisdn: str = raw_body.get("MSISDN", "")
        first_name: str = raw_body.get("FirstName", "")
        last_name: str = raw_body.get("LastName", "")
        counterparty_name = f"{first_name} {last_name}".strip() or None

        idempotency_key = _build_idempotency_key("c2b", transaction_id)

        if await _is_duplicate(db, idempotency_key):
            logger.info("daraja.c2b_confirmation_duplicate", txn_id=transaction_id)
            return _daraja_ok()

        till = await _fetch_till_by_shortcode(db, shortcode)
        if not till:
            logger.error(
                "daraja.c2b_confirmation_till_missing",
                shortcode=shortcode,
                txn_id=transaction_id,
            )
            return _daraja_ok()

        try:
            txn_date = datetime.strptime(trans_time, "%Y%m%d%H%M%S")
        except ValueError:
            txn_date = datetime.now(timezone.utc).replace(tzinfo=None)

        amount_kes = Decimal(amount_str)

        transaction = Transaction(
            public_id=str(ULID()),
            user_id=till.user_id,
            till_id=till.id,
            mpesa_receipt_number=transaction_id,
            transaction_type=TransactionType.c2b_receive,
            direction=TransactionDirection.credit,
            amount_kes=amount_kes,
            fee_kes=Decimal("0.00"),
            counterparty_name=counterparty_name,
            counterparty_phone=msisdn,
            description=f"C2B payment. Ref: {bill_ref}",
            status=TransactionStatus.completed,
            source=TransactionSource.daraja_callback,
            raw_payload=raw_body,
            idempotency_key=idempotency_key,
            transaction_date=txn_date,
        )
        db.add(transaction)
        await db.flush()

        # Auto-lock tax portion on every inflow
        tax_service = TaxService(db)
        await tax_service.lock_tax_on_inflow(
            user_id=till.user_id,
            till_id=till.id,
            transaction=transaction,
        )

        # Evaluate smart float rules after confirmed inflow
        till_service = TillService(db, get_daraja_service())
        triggered_rules = await till_service.evaluate_smart_float_rules(
            till=till,
            current_balance=(till.last_known_balance_kes or Decimal("0")) + amount_kes,
        )

        if triggered_rules:
            redis = get_redis()
            import json
            await redis.publish(
                f"smart_float:triggered:{till.id}",
                json.dumps({
                    "till_id": till.id,
                    "balance": str((till.last_known_balance_kes or Decimal("0")) + amount_kes),
                    "rule_ids": [r.id for r in triggered_rules],
                }),
            )

        await audit.record(
            user_id=till.user_id,
            actor_type="daraja_callback",
            action="c2b_payment_received",
            entity_type="transaction",
            entity_id=transaction.id,
            payload_summary={
                "receipt": transaction_id,
                "amount": str(amount_kes),
                "shortcode": shortcode,
            },
        )

        logger.info(
            "daraja.c2b_confirmed",
            txn_id=transaction_id,
            amount=str(amount_kes),
            till_id=till.id,
        )

    except Exception as exc:
        logger.error(
            "daraja.c2b_confirmation_error",
            error=str(exc),
            body=str(raw_body)[:500],
        )

    return _daraja_ok()


# ── B2C Result ────────────────────────────────────────────────

@router.post(
    "/b2c-result",
    summary="Receive B2C disbursement result from Safaricom",
    include_in_schema=False,
)
async def b2c_result(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Called by Safaricom after a B2C transfer completes or fails.
    Updates the pending transaction record created when B2C was initiated.
    """
    raw_body: dict = await request.json()
    audit = AuditService(db)

    try:
        result: dict = raw_body.get("Result", {})
        result_code: int = result.get("ResultCode", -1)
        result_desc: str = result.get("ResultDesc", "")
        transaction_id: str = result.get("TransactionID", "")
        conversation_id: str = result.get("ConversationID", "")
        originator_id: str = result.get("OriginatorConversationID", "")

        idempotency_key = _build_idempotency_key("b2c", transaction_id or originator_id)

        if await _is_duplicate(db, idempotency_key):
            logger.info("daraja.b2c_result_duplicate", txn_id=transaction_id)
            return _daraja_ok()

        result_params: list = (
            result.get("ResultParameters", {}).get("ResultParameter", [])
        )
        meta = {p["Key"]: p.get("Value") for p in result_params}

        amount_kes = Decimal(str(meta.get("TransactionAmount", "0")))
        phone_number: str = str(meta.get("ReceiverPartyPublicName", "")).split("-")[0].strip()
        shortcode: str = str(meta.get("B2CChargesPaidAccountAvailableFunds", "")).strip()

        # Find the till by originator conversation ID stored in Redis
        redis = get_redis()
        import json
        b2c_meta_raw = await redis.get(f"b2c:session:{originator_id}")
        till_id: int | None = None
        user_id: int | None = None

        if b2c_meta_raw:
            b2c_meta = json.loads(b2c_meta_raw)
            till_id = b2c_meta.get("till_id")
            user_id = b2c_meta.get("user_id")
            await redis.delete(f"b2c:session:{originator_id}")

        if not till_id:
            logger.warning(
                "daraja.b2c_result_no_session",
                originator_id=originator_id,
            )
            return _daraja_ok()

        txn_status = (
            TransactionStatus.completed
            if result_code == 0
            else TransactionStatus.failed
        )

        transaction = Transaction(
            public_id=str(ULID()),
            user_id=user_id,
            till_id=till_id,
            mpesa_receipt_number=transaction_id or None,
            transaction_type=TransactionType.b2c_send,
            direction=TransactionDirection.debit,
            amount_kes=amount_kes,
            fee_kes=Decimal("0.00"),
            counterparty_phone=phone_number,
            description=meta.get("B2CPaymentLocalTransferAccountAvailableFunds", "B2C transfer"),
            status=txn_status,
            failure_reason=result_desc if result_code != 0 else None,
            source=TransactionSource.daraja_callback,
            raw_payload=raw_body,
            idempotency_key=idempotency_key,
            transaction_date=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(transaction)
        await db.flush()

        await audit.record(
            user_id=user_id,
            actor_type="daraja_callback",
            action="b2c_transfer_completed" if result_code == 0 else "b2c_transfer_failed",
            entity_type="transaction",
            entity_id=transaction.id,
            payload_summary={
                "result_code": result_code,
                "amount": str(amount_kes),
                "receipt": transaction_id,
            },
        )

        logger.info(
            "daraja.b2c_result",
            result_code=result_code,
            amount=str(amount_kes),
            till_id=till_id,
        )

    except Exception as exc:
        logger.error(
            "daraja.b2c_result_error",
            error=str(exc),
            body=str(raw_body)[:500],
        )

    return _daraja_ok()


# ── Balance Result ────────────────────────────────────────────

@router.post(
    "/balance-result",
    summary="Receive account balance query result from Safaricom",
    include_in_schema=False,
)
async def balance_result(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Safaricom calls this after processing an Account Balance query.
    Parses the balance, updates the till record and Redis cache.
    Evaluates smart float rules on the fresh balance.
    """
    raw_body: dict = await request.json()

    try:
        result: dict = raw_body.get("Result", {})
        result_code: int = result.get("ResultCode", -1)
        originator_id: str = result.get("OriginatorConversationID", "")

        if result_code != 0:
            logger.warning(
                "daraja.balance_result_failed",
                result_code=result_code,
                desc=result.get("ResultDesc"),
            )
            return _daraja_ok()

        result_params: list = (
            result.get("ResultParameters", {}).get("ResultParameter", [])
        )

        from app.services.daraja_service import DarajaService
        balances = DarajaService.parse_balance_result(result_params)

        if not balances:
            logger.warning("daraja.balance_result_empty", originator_id=originator_id)
            return _daraja_ok()

        # Retrieve which till this balance belongs to
        redis = get_redis()
        import json
        session_raw = await redis.get(f"balance:session:{originator_id}")
        if not session_raw:
            logger.warning(
                "daraja.balance_result_no_session",
                originator_id=originator_id,
            )
            return _daraja_ok()

        session_meta = json.loads(session_raw)
        till_id: int = session_meta["till_id"]
        user_id: int = session_meta["user_id"]
        await redis.delete(f"balance:session:{originator_id}")

        # Use "Working Account" as primary balance — Daraja's main account type
        working_balance = balances.get(
            "Working Account",
            next(iter(balances.values()), Decimal("0.00")),
        )

        till_service = TillService(db, get_daraja_service())
        await till_service.update_cached_balance(till_id, working_balance)

        # Evaluate smart float rules on the fresh balance
        till_result = await db.execute(select(Till).where(Till.id == till_id))
        till = till_result.scalar_one_or_none()

        if till:
            triggered_rules = await till_service.evaluate_smart_float_rules(
                till=till,
                current_balance=working_balance,
            )
            if triggered_rules:
                await redis.publish(
                    f"smart_float:triggered:{till.id}",
                    json.dumps({
                        "till_id": till_id,
                        "balance": str(working_balance),
                        "rule_ids": [r.id for r in triggered_rules],
                    }),
                )

        # Resume any agent session waiting on this balance
        agent_session_raw = await redis.get(f"agent:balance_wait:{till_id}")
        if agent_session_raw:
            await redis.publish(
                f"agent:balance_ready:{till_id}",
                str(working_balance),
            )
            await redis.delete(f"agent:balance_wait:{till_id}")

        logger.info(
            "daraja.balance_result_processed",
            till_id=till_id,
            working_balance=str(working_balance),
        )

    except Exception as exc:
        logger.error(
            "daraja.balance_result_error",
            error=str(exc),
            body=str(raw_body)[:500],
        )

    return _daraja_ok()


# ── Timeout Handlers ──────────────────────────────────────────

@router.post("/b2c-timeout", include_in_schema=False)
async def b2c_timeout(request: Request):
    """Safaricom calls this if B2C result is not delivered in time."""
    body = await request.json()
    logger.warning("daraja.b2c_timeout", body=str(body)[:300])
    return _daraja_ok()


@router.post("/balance-timeout", include_in_schema=False)
async def balance_timeout(request: Request):
    """Safaricom calls this if balance query result is not delivered in time."""
    body = await request.json()
    logger.warning("daraja.balance_timeout", body=str(body)[:300])
    return _daraja_ok()


@router.post("/transaction-status-result", include_in_schema=False)
async def transaction_status_result(request: Request):
    """Receive transaction status query result."""
    body = await request.json()
    logger.info("daraja.transaction_status_result", body=str(body)[:300])
    return _daraja_ok()


@router.post("/transaction-status-timeout", include_in_schema=False)
async def transaction_status_timeout(request: Request):
    """Safaricom calls this if transaction status result is not delivered in time."""
    body = await request.json()
    logger.warning("daraja.transaction_status_timeout", body=str(body)[:300])
    return _daraja_ok()