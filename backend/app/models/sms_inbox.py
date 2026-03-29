"""
SmsInbox ORM model — forwarded M-Pesa SMS messages awaiting parsing.
Maps to the `sms_inbox` table.
"""
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class ParseStatus(str, enum.Enum):
    pending = "pending"
    parsed = "parsed"
    ambiguous = "ambiguous"
    failed = "failed"


class SmsInbox(Base):
    __tablename__ = "sms_inbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    raw_sms_text: Mapped[str] = mapped_column(Text, nullable=False)
    sender_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus), nullable=False, default=ParseStatus.pending
    )
    parsed_transaction_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    parse_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="sms_inbox")

    def __repr__(self) -> str:
        return f"<SmsInbox id={self.id} status={self.parse_status} user={self.user_id}>"