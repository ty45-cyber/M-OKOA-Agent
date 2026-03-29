"""
TaxLock ORM model — virtual sub-wallet for KRA compliance.
DST 1.5%, VAT 16% automatically locked from M-Pesa inflows.
Maps to the `tax_locks` table.
"""
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal
import enum

from app.core.database import Base


class TaxType(str, enum.Enum):
    dst = "dst"
    vat = "vat"
    income_tax = "income_tax"
    presumptive = "presumptive"


class TaxLockStatus(str, enum.Enum):
    locked = "locked"
    filed = "filed"
    released = "released"


class TaxLock(Base):
    __tablename__ = "tax_locks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    till_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tills.id", ondelete="RESTRICT"), nullable=False
    )
    tax_type: Mapped[TaxType] = mapped_column(Enum(TaxType), nullable=False)
    taxable_amount_kes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    locked_amount_kes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[TaxLockStatus] = mapped_column(
        Enum(TaxLockStatus), nullable=False, default=TaxLockStatus.locked
    )
    filed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="tax_locks")
    till: Mapped["Till"] = relationship("Till", back_populates="tax_locks")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="tax_lock", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<TaxLock id={self.id} type={self.tax_type} "
            f"locked={self.locked_amount_kes} period={self.period_month}>"
        )