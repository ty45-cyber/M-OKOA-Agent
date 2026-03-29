"""
Smart Float Executor — Redis pub/sub listener that executes triggered float rules.

daraja_webhooks.py publishes to 'smart_float:triggered:{till_id}' when a
balance update or C2B payment triggers a rule. This service subscribes,
reads the rule, and fires the B2C disbursement via Daraja.

Run as a background task inside the FastAPI lifespan.
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.redis_client import get_redis
from app.models.smart_float_rule import SmartFloatRule
from app.models.till import Till
from app.models.transaction import (
    Transaction,
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)
from app.services.audit_service import AuditService
from app.services.daraja_service import (
    DarajaError,
    DarajaService,
    DarajaTillCredentials,
    get_daraja_service,
)
from ulid import ULID
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)
settings = get_settings()

# How long to wait between rule executions for the same till (seconds)
RULE_COOLDOWN_SECONDS = 300


async def _is_on_cooldown(redis, rule_id: int) -> bool:
    key = f"smart_float:cooldown:{rule_id}"
    return await redis.exists(key) == 1


async def _set_cooldown(redis, rule_id: int) -> None:
    key = f"smart_float:cooldown:{rule_id}"
    await redis.setex(key, RULE_COOLDOWN_SECONDS, "1")


async def _execute_rule(
    rule: SmartFloatRule,
    till: Till,
    current_balance: Decimal,
    daraja: DarajaService,
) -> None:
    """
    Execute a single triggered smart float rule.
    Calculates transfer amount and fires B2C disbursement.
    """
    if not all([
        till.daraja_consumer_key,
        till.daraja_consumer_secret,
        till.daraja_shortcode,
        till.daraja_passkey,
    ]):
        logger.warning(
            "smart_float.missing_credentials",
            rule_id=rule.id,
            till_id=till.id,
        )
        return

    # Calculate how much to transfer
    if rule.transfer_amount_kes:
        transfer_amount = rule.transfer_amount_kes
    else:
        # Transfer all excess above the threshold
        transfer_amount = current_balance - rule.trigger_threshold_kes

    if transfer_amount <= Decimal("0"):
        logger.info(
            "smart_float.nothing_to_transfer",
            rule_id=rule.id,
            balance=str(current_balance),
            threshold=str(rule.trigger_threshold_kes),
        )
        return

    creds = DarajaTillCredentials(
        encrypted_consumer_key=till.daraja_consumer_key,
        encrypted_consumer_secret=till.daraja_consumer_secret,
        shortcode=till.daraja_shortcode,
        encrypted_passkey=till.daraja_passkey,
    )

    originator_id = str(ULID())

    async with AsyncSessionFactory() as db:
        audit = AuditService(db)

        try:
            response = await daraja.initiate_b2c(
                creds=creds,
                initiator_name="MokoaAgent",
                security_credential="",  # Set at Daraja go-live
                phone_number=rule.destination_ref,
                amount=transfer_amount,
                command_id="BusinessPayment",
                remarks=f"Smart Float: {rule.rule_name}"[:100],
            )

            # Store B2C session for callback correlation
            redis = get_redis()
            await redis.setex(
                f"b2c:session:{originator_id}",
                600,
                json.dumps({
                    "till_id": till.id,
                    "user_id": till.user_id,
                    "amount": str(transfer_amount),
                    "destination": rule.destination_ref,
                    "rule_id": rule.id,
                }),
            )

            # Record a pending transaction
            transaction = Transaction(
                public_id=str(ULID()),
                user_id=till.user_id,
                till_id=till.id,
                transaction_type=TransactionType.float_transfer,
                direction=TransactionDirection.debit,
                amount_kes=transfer_amount,
                fee_kes=Decimal("0.00"),
                counterparty_name=rule.destination_name or rule.destination_ref,
                description=f"Smart Float auto-transfer: {rule.rule_name}",
                status=TransactionStatus.pending,
                source=TransactionSource.agent_action,
                idempotency_key=f"smartfloat:{originator_id}",
                transaction_date=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(transaction)

            # Update rule metadata
            rule_result = await db.execute(
                select(SmartFloatRule).where(SmartFloatRule.id == rule.id)
            )
            db_rule = rule_result.scalar_one_or_none()
            if db_rule:
                db_rule.last_triggered_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db_rule.trigger_count = (db_rule.trigger_count or 0) + 1

            await audit.record(
                user_id=till.user_id,
                actor_type="system",
                action="smart_float_executed",
                entity_type="smart_float_rule",
                entity_id=rule.id,
                payload_summary={
                    "rule_name": rule.rule_name,
                    "amount": str(transfer_amount),
                    "destination": rule.destination_ref,
                },
            )

            await db.commit()

            logger.info(
                "smart_float.executed",
                rule_id=rule.id,
                till_id=till.id,
                amount=str(transfer_amount),
                destination=rule.destination_ref,
            )

        except DarajaError as exc:
            logger.error(
                "smart_float.daraja_error",
                rule_id=rule.id,
                error=str(exc),
            )
        except Exception as exc:
            logger.error(
                "smart_float.unexpected_error",
                rule_id=rule.id,
                error=str(exc),
            )
            await db.rollback()


async def smart_float_listener() -> None:
    """
    Long-running Redis pub/sub listener.
    Subscribes to smart_float:triggered:* channels.
    Started as a background task from the FastAPI lifespan.
    """
    redis = get_redis()
    daraja = get_daraja_service()
    pubsub = redis.pubsub()

    # Subscribe to the pattern — covers all till IDs
    await pubsub.psubscribe("smart_float:triggered:*")
    logger.info("smart_float.listener_started")

    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue

            try:
                data: dict = json.loads(message["data"])
                till_id: int = data["till_id"]
                current_balance = Decimal(str(data["balance"]))
                rule_ids: list[int] = data.get("rule_ids", [])

                if not rule_ids:
                    continue

                async with AsyncSessionFactory() as db:
                    for rule_id in rule_ids:
                        # Skip if on cooldown
                        if await _is_on_cooldown(redis, rule_id):
                            logger.info(
                                "smart_float.rule_on_cooldown",
                                rule_id=rule_id,
                            )
                            continue

                        rule_result = await db.execute(
                            select(SmartFloatRule).where(
                                SmartFloatRule.id == rule_id,
                                SmartFloatRule.is_active == True,
                            )
                        )
                        rule = rule_result.scalar_one_or_none()
                        if not rule:
                            continue

                        till_result = await db.execute(
                            select(Till).where(Till.id == till_id)
                        )
                        till = till_result.scalar_one_or_none()
                        if not till:
                            continue

                        await _set_cooldown(redis, rule_id)
                        await _execute_rule(rule, till, current_balance, daraja)

            except Exception as exc:
                logger.error(
                    "smart_float.message_processing_error",
                    error=str(exc),
                )
                continue

    except asyncio.CancelledError:
        logger.info("smart_float.listener_stopped")
        await pubsub.punsubscribe("smart_float:triggered:*")
        raise