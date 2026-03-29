"""
Transaction ORM model — every money movement tracked here.
Source of truth for the ledger.
Maps to the `transactions` table.
"""
from sqlalchemy import (
    BigInteger, DateTime, Enum, ForeignKey,
    JSON, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from decimal import Decimal
import enum

from app.core.database import Base


class TransactionType(str, enum.Enum):
    c2b_receive = "c2b_receive"
    b2c_send = "b2c_send"
    stk_push = "stk_push"
    bill_payment = "bill_payment"
    float_transfer = "float_transfer"
    tax_lock = "tax_lock"
    sms_import = "sms_import"


class TransactionDirection(str, enum.Enum):
    credit = "credit"
    debit = "debit"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    reversed = "reversed"


class TransactionSource(str, enum.Enum):
    daraja_callback = "daraja_callback"
    sms_parser = "sms_parser"
    agent_action = "agent_action"
    manual = "manual"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    till_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tills.id", ondelete="RESTRICT"), nullable=False
    )
    mpesa_receipt_number: Mapped[str | None] = mapped_column(
        String(30), unique=True, nullable=True
    )
    mpesa_transaction_id: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), nullable=False
    )
    direction: Mapped[TransactionDirection] = mapped_column(
        Enum(TransactionDirection), nullable=False
    )
    amount_kes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee_kes: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    counterparty_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    counterparty_phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), nullable=False, default=TransactionStatus.pending
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_lock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tax_locks.id"), nullable=True
    )
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource), nullable=False
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    till: Mapped["Till"] = relationship("Till", back_populates="transactions")
    tax_lock: Mapped["TaxLock | None"] = relationship(
        "TaxLock", back_populates="transactions", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} type={self.transaction_type} "
            f"amount={self.amount_kes} status={self.status}>"
        )