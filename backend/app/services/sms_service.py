"""
SMS Service — parse forwarded M-Pesa confirmation messages into ledger entries.

Two-pass parsing strategy:
  Pass 1: Regex patterns for all known M-Pesa SMS formats (fast, free)
  Pass 2: Claude fallback for ambiguous or new SMS formats (accurate, paid)

Known M-Pesa SMS patterns covered:
  - C2B received: "confirmed. KES X received from NAME PHONE on DATE"
  - B2C sent:     "confirmed. KES X sent to NAME PHONE on DATE"
  - Paybill pay:  "confirmed. KES X sent to PAYBILL for account ACC on DATE"
  - Buy Goods:    "confirmed. KES X paid to MERCHANT on DATE"
  - Reversal:     "reversed. KES X from PHONE on DATE"
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.config import get_settings
from app.models.sms_inbox import SmsInbox, ParseStatus
from app.models.till import Till
from app.models.transaction import (
    Transaction,
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)
from app.schemas.sms import SmsParsedResult, SmsForwardRequest
from app.services.tax_service import TaxService

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── Regex patterns ────────────────────────────────────────────

# Example: "RBA67XXXXX Confirmed. KES1,234.00 received from JOHN DOE 0712345678 on 1/1/25 at 10:30 AM"
_PATTERN_C2B = re.compile(
    r"(?P<receipt>[A-Z0-9]{10,12})\s+Confirmed\."
    r"\s+KES(?P<amount>[\d,]+\.?\d*)\s+received from\s+"
    r"(?P<name>[A-Z ]+?)\s+(?P<phone>(?:\+?254|0)\d{9})"
    r".*?on\s+(?P<date>[\d/]+)\s+at\s+(?P<time>[\d:]+\s*[AP]M)",
    re.IGNORECASE,
)

# Example: "RBA67XXXXX Confirmed. KES500.00 sent to JANE DOE 0798765432 on 1/1/25 at 9:00 AM"
_PATTERN_B2C = re.compile(
    r"(?P<receipt>[A-Z0-9]{10,12})\s+Confirmed\."
    r"\s+KES(?P<amount>[\d,]+\.?\d*)\s+sent to\s+"
    r"(?P<name>[A-Z ]+?)\s+(?P<phone>(?:\+?254|0)\d{9})"
    r".*?on\s+(?P<date>[\d/]+)\s+at\s+(?P<time>[\d:]+\s*[AP]M)",
    re.IGNORECASE,
)

# Example: "RBA67XXXXX Confirmed. KES1,000.00 sent to 174379 for account 12345678 on 1/1/25"
_PATTERN_PAYBILL = re.compile(
    r"(?P<receipt>[A-Z0-9]{10,12})\s+Confirmed\."
    r"\s+KES(?P<amount>[\d,]+\.?\d*)\s+sent to\s+"
    r"(?P<paybill>\d{4,7})\s+for account\s+(?P<account>\S+)"
    r".*?on\s+(?P<date>[\d/]+)",
    re.IGNORECASE,
)

# Example: "RBA67XXXXX Confirmed. KES200.00 paid to QUICKMART on 1/1/25 at 11:00 AM"
_PATTERN_BUY_GOODS = re.compile(
    r"(?P<receipt>[A-Z0-9]{10,12})\s+Confirmed\."
    r"\s+KES(?P<amount>[\d,]+\.?\d*)\s+paid to\s+"
    r"(?P<merchant>[A-Z0-9 ]+?)\s+on\s+(?P<date>[\d/]+)",
    re.IGNORECASE,
)

# Balance after transaction
_PATTERN_BALANCE = re.compile(
    r"M-PESA balance is KES(?P<balance>[\d,]+\.?\d*)",
    re.IGNORECASE,
)


def _clean_amount(raw: str) -> Decimal:
    """Remove commas and convert to Decimal."""
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return Decimal("0.00")


def _parse_mpesa_date(date_str: str, time_str: str = "") -> datetime:
    """
    Parse M-Pesa date strings into datetime objects.
    Formats vary: '1/1/25', '1/1/2025', '01/01/2025'
    """
    combined = f"{date_str} {time_str}".strip()
    formats = [
        "%d/%m/%y %I:%M %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(combined, fmt)
        except ValueError:
            continue
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Regex-based parser ────────────────────────────────────────

def _parse_with_regex(raw_sms: str) -> SmsParsedResult | None:
    """
    Attempt to parse an M-Pesa SMS using regex patterns.
    Returns None if no pattern matches.
    """
    # C2B received
    match = _PATTERN_C2B.search(raw_sms)
    if match:
        g = match.groupdict()
        balance_match = _PATTERN_BALANCE.search(raw_sms)
        return SmsParsedResult(
            mpesa_receipt=g["receipt"].upper(),
            amount_kes=str(_clean_amount(g["amount"])),
            direction="credit",
            counterparty_name=g["name"].strip().title(),
            counterparty_phone=g["phone"],
            transaction_date=str(_parse_mpesa_date(g["date"], g.get("time", ""))),
            balance_after=str(_clean_amount(balance_match.group("balance")))
            if balance_match else None,
            raw_sms=raw_sms,
            confidence="high",
        )

    # B2C sent
    match = _PATTERN_B2C.search(raw_sms)
    if match:
        g = match.groupdict()
        balance_match = _PATTERN_BALANCE.search(raw_sms)
        return SmsParsedResult(
            mpesa_receipt=g["receipt"].upper(),
            amount_kes=str(_clean_amount(g["amount"])),
            direction="debit",
            counterparty_name=g["name"].strip().title(),
            counterparty_phone=g["phone"],
            transaction_date=str(_parse_mpesa_date(g["date"], g.get("time", ""))),
            balance_after=str(_clean_amount(balance_match.group("balance")))
            if balance_match else None,
            raw_sms=raw_sms,
            confidence="high",
        )

    # Paybill payment
    match = _PATTERN_PAYBILL.search(raw_sms)
    if match:
        g = match.groupdict()
        balance_match = _PATTERN_BALANCE.search(raw_sms)
        return SmsParsedResult(
            mpesa_receipt=g["receipt"].upper(),
            amount_kes=str(_clean_amount(g["amount"])),
            direction="debit",
            counterparty_name=f"Paybill {g['paybill']}",
            counterparty_phone=None,
            transaction_date=str(_parse_mpesa_date(g["date"])),
            balance_after=str(_clean_amount(balance_match.group("balance")))
            if balance_match else None,
            raw_sms=raw_sms,
            confidence="high",
        )

    # Buy Goods
    match = _PATTERN_BUY_GOODS.search(raw_sms)
    if match:
        g = match.groupdict()
        balance_match = _PATTERN_BALANCE.search(raw_sms)
        return SmsParsedResult(
            mpesa_receipt=g["receipt"].upper(),
            amount_kes=str(_clean_amount(g["amount"])),
            direction="debit",
            counterparty_name=g["merchant"].strip().title(),
            counterparty_phone=None,
            transaction_date=str(_parse_mpesa_date(g["date"])),
            balance_after=str(_clean_amount(balance_match.group("balance")))
            if balance_match else None,
            raw_sms=raw_sms,
            confidence="high",
        )

    return None


# ── Claude fallback parser ────────────────────────────────────

async def _parse_with_claude(raw_sms: str) -> SmsParsedResult | None:
    """
    Use Claude to parse ambiguous or unrecognized M-Pesa SMS formats.
    Called only when regex parsing fails.
    """
    import anthropic
    import json as json_lib

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = f"""Parse this M-Pesa SMS confirmation message and extract transaction data.
Return ONLY a JSON object with these exact keys:
{{
  "mpesa_receipt": "string or null",
  "amount_kes": "decimal string or null",
  "direction": "credit or debit or null",
  "counterparty_name": "string or null",
  "counterparty_phone": "string or null",
  "transaction_date": "ISO datetime string or null",
  "balance_after": "decimal string or null",
  "confidence": "high or medium or low"
}}

SMS message:
{raw_sms}

Return only the JSON. No explanation."""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_json = response.content[0].text.strip()
        raw_json = raw_json.replace("```json", "").replace("```", "").strip()
        data = json_lib.loads(raw_json)

        return SmsParsedResult(
            mpesa_receipt=data.get("mpesa_receipt"),
            amount_kes=data.get("amount_kes"),
            direction=data.get("direction"),
            counterparty_name=data.get("counterparty_name"),
            counterparty_phone=data.get("counterparty_phone"),
            transaction_date=data.get("transaction_date"),
            balance_after=data.get("balance_after"),
            raw_sms=raw_sms,
            confidence=data.get("confidence", "low"),
        )
    except Exception as exc:
        logger.warning("sms.claude_parse_failed", error=str(exc))
        return None


# ── SMS Service ───────────────────────────────────────────────

class SmsService:
    """
    Handles forwarded M-Pesa SMS messages.
    Parses them into structured transaction records.
    Stateless — db session injected per call.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def ingest_sms(
        self,
        user_id: int,
        payload: SmsForwardRequest,
        till_id: int | None = None,
    ) -> tuple[SmsInbox, SmsParsedResult | None]:
        """
        Store the raw SMS and attempt to parse it.

        Returns the inbox record and the parsed result (or None on failure).
        """
        received_at = payload.received_at or datetime.now(timezone.utc).replace(tzinfo=None)

        inbox_record = SmsInbox(
            public_id=str(ULID()),
            user_id=user_id,
            raw_sms_text=payload.raw_sms_text,
            sender_number=payload.sender_number,
            parse_status=ParseStatus.pending,
            received_at=received_at,
        )
        self._db.add(inbox_record)
        await self._db.flush()

        # Pass 1: regex
        parsed = _parse_with_regex(payload.raw_sms_text)

        # Pass 2: Claude fallback
        if parsed is None:
            logger.info("sms.regex_miss_falling_back_to_claude", inbox_id=inbox_record.id)
            parsed = await _parse_with_claude(payload.raw_sms_text)

        if parsed is None or not parsed.amount_kes:
            inbox_record.parse_status = ParseStatus.failed
            inbox_record.parse_error = "Could not extract transaction data from SMS."
            inbox_record.parsed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            logger.warning("sms.parse_failed", inbox_id=inbox_record.id)
            return inbox_record, None

        if parsed.confidence == "low":
            inbox_record.parse_status = ParseStatus.ambiguous
            inbox_record.parse_error = "Low confidence parse — manual review recommended."
            inbox_record.parsed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            return inbox_record, parsed

        # Resolve till — use provided till_id or find by user's first active till
        resolved_till_id = await self._resolve_till_id(user_id, till_id)
        if not resolved_till_id:
            inbox_record.parse_status = ParseStatus.failed
            inbox_record.parse_error = "No active till found to associate this transaction."
            return inbox_record, parsed

        # Check for duplicate receipt number
        if parsed.mpesa_receipt:
            existing = await self._find_by_receipt(parsed.mpesa_receipt)
            if existing:
                inbox_record.parse_status = ParseStatus.failed
                inbox_record.parse_error = f"Duplicate: receipt {parsed.mpesa_receipt} already exists."
                return inbox_record, parsed

        # Create transaction record
        direction = (
            TransactionDirection.credit
            if parsed.direction == "credit"
            else TransactionDirection.debit
        )

        try:
            txn_date_raw = parsed.transaction_date
            txn_date = (
                datetime.fromisoformat(txn_date_raw)
                if txn_date_raw
                else datetime.now(timezone.utc).replace(tzinfo=None)
            )
        except (ValueError, TypeError):
            txn_date = datetime.now(timezone.utc).replace(tzinfo=None)

        transaction = Transaction(
            public_id=str(ULID()),
            user_id=user_id,
            till_id=resolved_till_id,
            mpesa_receipt_number=parsed.mpesa_receipt,
            transaction_type=TransactionType.sms_import,
            direction=direction,
            amount_kes=Decimal(parsed.amount_kes),
            fee_kes=Decimal("0.00"),
            counterparty_name=parsed.counterparty_name,
            counterparty_phone=parsed.counterparty_phone,
            description=f"SMS import: {payload.raw_sms_text[:100]}",
            status=TransactionStatus.completed,
            source=TransactionSource.sms_parser,
            idempotency_key=f"sms:{parsed.mpesa_receipt}" if parsed.mpesa_receipt else None,
            transaction_date=txn_date,
        )
        self._db.add(transaction)
        await self._db.flush()

        # Lock tax on credited inflows
        if direction == TransactionDirection.credit:
            tax_service = TaxService(self._db)
            await tax_service.lock_tax_on_inflow(
                user_id=user_id,
                till_id=resolved_till_id,
                transaction=transaction,
            )

        inbox_record.parse_status = ParseStatus.parsed
        inbox_record.parsed_transaction_id = transaction.id
        inbox_record.parsed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        logger.info(
            "sms.parsed_successfully",
            inbox_id=inbox_record.id,
            transaction_id=transaction.id,
            receipt=parsed.mpesa_receipt,
            amount=parsed.amount_kes,
            confidence=parsed.confidence,
        )

        return inbox_record, parsed

    async def list_inbox(
        self,
        user_id: int,
        parse_status: ParseStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SmsInbox], int]:
        """Return paginated SMS inbox for a user."""
        from sqlalchemy import select, func

        query = (
            select(SmsInbox)
            .where(SmsInbox.user_id == user_id)
        )
        if parse_status:
            query = query.where(SmsInbox.parse_status == parse_status)

        count_result = await self._db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        paginated = (
            query
            .order_by(SmsInbox.received_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._db.execute(paginated)
        items = result.scalars().all()

        return list(items), total

    # ── Private helpers ──────────────────────────────────────

    async def _resolve_till_id(
        self,
        user_id: int,
        provided_till_id: int | None,
    ) -> int | None:
        if provided_till_id:
            return provided_till_id

        from sqlalchemy import select
        result = await self._db.execute(
            select(Till.id)
            .where(Till.user_id == user_id, Till.is_active == True)
            .order_by(Till.created_at.asc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def _find_by_receipt(self, receipt: str) -> Transaction | None:
        from sqlalchemy import select
        result = await self._db.execute(
            select(Transaction).where(
                Transaction.mpesa_receipt_number == receipt
            )
        )
        return result.scalar_one_or_none()