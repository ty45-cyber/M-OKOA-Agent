"""
BillPayee ORM model — pre-configured payees per user.
e.g. KPLC Prepaid, Nairobi Water, Rent Paybill.
Maps to the `bill_payees` table.
"""
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class PayeeCategory(str, enum.Enum):
    utility = "utility"
    rent = "rent"
    loan = "loan"
    supplier = "supplier"
    other = "other"


class BillPayee(Base):
    __tablename__ = "bill_payees"
    __table_args__ = (
        UniqueConstraint("user_id", "paybill_number", "account_number", name="uq_payee_per_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    payee_name: Mapped[str] = mapped_column(String(80), nullable=False)
    paybill_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[PayeeCategory] = mapped_column(
        Enum(PayeeCategory), nullable=False, default=PayeeCategory.other
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="bill_payees")

    def __repr__(self) -> str:
        return (
            f"<BillPayee id={self.id} name={self.payee_name} "
            f"paybill={self.paybill_number}>"
        )