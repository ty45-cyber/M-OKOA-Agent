"""
Telegram webhook router — receives updates from Telegram servers.
Mounted into the main FastAPI app so Telegram and Daraja
callbacks share the same HTTPS server.

Telegram sends POST requests to /telegram/webhook/<secret_token>
The secret_token prevents unauthorized actors from pushing fake updates.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request, Response, status
from telegram import Update

from app.bot.telegram_bot import build_telegram_application
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

# Built once at module load — reused across all requests
_telegram_app = build_telegram_application()


@router.post(
    "/webhook/{secret_token}",
    include_in_schema=False,
    status_code=status.HTTP_200_OK,
)
async def telegram_webhook(
    secret_token: str,
    request: Request,
) -> Response:
    """
    Receive a Telegram update and dispatch to the appropriate handler.
    Validates the secret_token before processing.
    """
    expected_token = settings.telegram_bot_token.split(":")[1][:16]

    if secret_token != expected_token:
        logger.warning(
            "telegram.webhook_invalid_token",
            received=secret_token[:6],
        )
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    try:
        body = await request.json()
        update = Update.de_json(body, _telegram_app.bot)
        await _telegram_app.process_update(update)
    except Exception as exc:
        logger.error("telegram.webhook_error", error=str(exc))

    # Always return 200 — Telegram will retry on non-200
    return Response(status_code=status.HTTP_200_OK)


async def register_webhook(base_url: str) -> None:
    """
    Register the webhook URL with Telegram on startup.
    Called from the FastAPI lifespan after Redis is ready.
    """
    secret_token = settings.telegram_bot_token.split(":")[1][:16]
    webhook_url = f"{base_url}/telegram/webhook/{secret_token}"

    await _telegram_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )
    logger.info("telegram.webhook_registered", url=webhook_url)