"""
AuditLog ORM model — immutable security event record.
Maps to the `audit_log` table.
Never updated. Never deleted.
"""
from sqlalchemy import BigInteger, DateTime, Enum, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_type: Mapped[str] = mapped_column(
        Enum("user", "agent", "system", "daraja_callback"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} user={self.user_id}>"