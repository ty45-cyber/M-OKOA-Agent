"""
Audit Service — immutable record of every sensitive action.
OWASP A09: Security Logging and Monitoring Failures.

Rules:
- Never update or delete audit records
- Never log raw secrets, passwords, or card data
- Every sensitive action in the system calls this service
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    """
    Write-only service for the audit log.
    Injected into any service that performs sensitive operations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self,
        actor_type: str,
        action: str,
        user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        payload_summary: dict[str, Any] | None = None,
    ) -> None:
        """
        Write one audit entry.
        Never raises — audit failure must not break the main operation.
        Logs a warning if the write fails so it can be investigated.
        """
        try:
            entry = AuditLog(
                user_id=user_id,
                actor_type=actor_type,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload_summary=self._sanitize(payload_summary or {}),
            )
            self._db.add(entry)
            await self._db.flush()
        except Exception as exc:
            logger.warning(
                "audit.write_failed",
                action=action,
                user_id=user_id,
                error=str(exc),
            )

    @staticmethod
    def _sanitize(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Strip any key that looks like it contains a secret before storing.
        Protects against accidental logging of credentials.
        """
        blocked_keys = {
            "password", "password_hash", "secret", "token",
            "consumer_key", "consumer_secret", "passkey",
            "pin", "otp", "access_token", "refresh_token",
            "authorization", "credential",
        }
        return {
            k: "***REDACTED***" if k.lower() in blocked_keys else v
            for k, v in payload.items()
        }