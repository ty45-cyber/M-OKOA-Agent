"""
SMS Pydantic schemas — request validation and response serialization.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, field_validator

from app.models.sms_inbox import ParseStatus


class SmsForwardRequest(BaseModel):
    """
    Payload for forwarding an M-Pesa SMS confirmation to M-Okoa.
    Sent by the user via Telegram or web interface.
    """
    raw_sms_text: str
    sender_number: str | None = None
    received_at: datetime | None = None

    @field_validator("raw_sms_text")
    @classmethod
    def validate_sms_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("SMS text too short to be a valid M-Pesa message.")
        if len(v) > 1000:
            raise ValueError("SMS text exceeds maximum length.")
        return v


class SmsResponse(BaseModel):
    public_id: str
    raw_sms_text: str
    parse_status: ParseStatus
    parse_error: str | None
    received_at: datetime
    parsed_at: datetime | None
    parsed_transaction_id: int | None

    model_config = {"from_attributes": True}


class SmsParsedResult(BaseModel):
    """
    Structured data extracted from a raw M-Pesa SMS.
    Returned to the caller after parsing.
    """
    mpesa_receipt: str | None
    amount_kes: str | None
    direction: str | None       # 'credit' or 'debit'
    counterparty_name: str | None
    counterparty_phone: str | None
    transaction_date: str | None
    balance_after: str | None
    raw_sms: str
    confidence: str             # 'high', 'medium', 'low'