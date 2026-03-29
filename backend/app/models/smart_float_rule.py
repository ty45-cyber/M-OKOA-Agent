"""
SmartFloatRule ORM model — user-defined automation rules.
"If till balance > X, move Y to Z."
Maps to the `smart_float_rules` table.
"""
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum,
    ForeignKey, Integer, Numeric, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal
import enum

from app.core.database import Base


class DestinationType(str, enum.Enum):
    bank_account = "bank_account"
    mpesa_phone = "mpesa_phone"
    chama_paybill = "chama_paybill"


class SmartFloatRule(Base):
    __tablename__ = "smart_float_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    till_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tills.id", ondelete="CASCADE"), nullable=False
    )
    rule_name: Mapped[str] = mapped_column(String(80), nullable=False)
    trigger_threshold_kes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transfer_amount_kes: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True,
        comment="NULL = transfer all excess above threshold"
    )
    destination_type: Mapped[DestinationType] = mapped_column(
        Enum(DestinationType), nullable=False
    )
    destination_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    destination_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="smart_float_rules")
    till: Mapped["Till"] = relationship("Till", back_populates="smart_float_rules")

    def __repr__(self) -> str:
        return (
            f"<SmartFloatRule id={self.id} name={self.rule_name} "
            f"threshold={self.trigger_threshold_kes} active={self.is_active}>"
        )