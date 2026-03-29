"""
Till Pydantic schemas — request validation and response serialization.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.models.smart_float_rule import DestinationType
from app.models.till import TillType


# ── Requests ─────────────────────────────────────────────────

class TillCreateRequest(BaseModel):
    display_name: str
    till_number: str
    till_type: TillType
    daraja_consumer_key: str | None = None
    daraja_consumer_secret: str | None = None
    daraja_shortcode: str | None = None
    daraja_passkey: str | None = None
    float_threshold_kes: Decimal | None = None
    float_target_account: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 80:
            raise ValueError("Display name must be between 2 and 80 characters.")
        return v

    @field_validator("till_number")
    @classmethod
    def validate_till_number(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("Till number must contain digits only.")
        if len(v) < 4 or len(v) > 20:
            raise ValueError("Till number must be between 4 and 20 digits.")
        return v

    @field_validator("float_threshold_kes")
    @classmethod
    def validate_threshold(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Float threshold must be greater than zero.")
        return v


class TillUpdateRequest(BaseModel):
    display_name: str | None = None
    daraja_consumer_key: str | None = None
    daraja_consumer_secret: str | None = None
    daraja_shortcode: str | None = None
    daraja_passkey: str | None = None
    float_threshold_kes: Decimal | None = None
    float_target_account: str | None = None


class SmartFloatRuleRequest(BaseModel):
    rule_name: str
    trigger_threshold_kes: Decimal
    transfer_amount_kes: Decimal | None = None
    destination_type: DestinationType
    destination_ref: str
    destination_name: str | None = None

    @field_validator("trigger_threshold_kes")
    @classmethod
    def validate_threshold(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Trigger threshold must be greater than zero.")
        return v

    @field_validator("transfer_amount_kes")
    @classmethod
    def validate_transfer_amount(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Transfer amount must be greater than zero.")
        return v


# ── Responses ────────────────────────────────────────────────

class TillResponse(BaseModel):
    public_id: str
    display_name: str
    till_number: str
    till_type: TillType
    is_active: bool
    float_threshold_kes: Decimal | None
    float_target_account: str | None
    last_known_balance_kes: Decimal | None
    balance_updated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    till_public_id: str
    display_name: str
    balance_kes: Decimal
    source: str  # 'cache', 'last_known', 'daraja_live'
    updated_at: datetime | None


class SmartFloatRuleResponse(BaseModel):
    public_id: str
    rule_name: str
    trigger_threshold_kes: Decimal
    transfer_amount_kes: Decimal | None
    destination_type: DestinationType
    destination_ref: str
    destination_name: str | None
    is_active: bool
    last_triggered_at: datetime | None
    trigger_count: int

    model_config = {"from_attributes": True}