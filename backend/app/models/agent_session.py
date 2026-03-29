"""
AgentSession ORM model — LangGraph execution traces with resumable checkpoints.
Maps to the `agent_sessions` table.
"""
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class SessionSource(str, enum.Enum):
    telegram = "telegram"
    web = "web"
    api = "api"


class SessionStatus(str, enum.Enum):
    active = "active"
    awaiting_callback = "awaiting_callback"
    completed = "completed"
    failed = "failed"


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    session_source: Mapped[SessionSource] = mapped_column(
        Enum(SessionSource), nullable=False
    )
    graph_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_node: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.active
    )
    stk_correlation_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    user_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # ── Relationships ────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="agent_sessions")

    def __repr__(self) -> str:
        return (
            f"<AgentSession id={self.id} source={self.session_source} "
            f"node={self.current_node} status={self.status}>"
        )