"""
Till ORM model — an M-Pesa Till or Paybill number owned by a user.
Daraja credentials stored AES-256 encrypted (handled at service layer).
Maps to the `tills` table.
"""
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey,
    Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal
import enum

from app.core.database import Base


class TillType(str, enum.Enum):
    till = "till"
    paybill = "paybill"
    personal = "personal"


class Till(Base):
    __tablename__ = "tills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    till_number: Mapped[str] = mapped_column(String(20), nullable=False)
    till_type: Mapped[TillType] = mapped_column(Enum(TillType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Daraja credentials (encrypted at service layer before storage) ──
    daraja_consumer_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    daraja_consumer_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    daraja_shortcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    daraja_passkey: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Smart Float config ───────────────────────────────────
    float_threshold_kes: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    float_target_account: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Cached balance ───────────────────────────────────────
    last_known_balance_kes: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    balance_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="tills")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="till", lazy="noload"
    )
    tax_locks: Mapped[list["TaxLock"]] = relationship(
        "TaxLock", back_populates="till", lazy="noload"
    )
    smart_float_rules: Mapped[list["SmartFloatRule"]] = relationship(
        "SmartFloatRule", back_populates="till", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Till id={self.id} number={self.till_number} type={self.till_type}>"