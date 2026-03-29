"""
Async SQLAlchemy engine and session factory.
One connection pool per application lifetime.
"""
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # Detect stale connections before use
    pool_recycle=3600,        # Recycle connections every hour
    echo=not settings.is_production,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # Avoid implicit lazy loads post-commit
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a session, guarantees cleanup.
    Always use this via Depends(get_db_session).
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()