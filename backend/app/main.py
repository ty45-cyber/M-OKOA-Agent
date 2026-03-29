"""
M-Okoa Agent — FastAPI application entry point. Final version.
Includes Smart Float background listener in lifespan.
"""
from __future__ import annotations
from app.api.v1.miniapp_auth import router as miniapp_router


import asyncio
from contextlib import asynccontextmanager

import structlog
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.redis_client import init_redis, close_redis
from app.api.v1 import auth, tills, transactions, daraja_webhooks, agent, sms
from app.bot.webhook import register_webhook, router as telegram_router
from app.services.smart_float_executor import smart_float_listener

logger = structlog.get_logger(__name__)
settings = get_settings()

_background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mokoa.startup", environment=settings.environment)

    # Infrastructure
    await init_redis()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Telegram webhook registration
    if settings.is_production:
        try:
            await register_webhook(settings.daraja_callback_base_url)
        except Exception as exc:
            logger.warning("telegram.webhook_registration_failed", error=str(exc))

    # Smart Float background listener
    task = asyncio.create_task(smart_float_listener())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    logger.info("mokoa.ready")
    yield

    # Graceful shutdown
    for task in _background_tasks:
        task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)

    await close_redis()
    await engine.dispose()
    logger.info("mokoa.shutdown")


app = FastAPI(
    title="M-Okoa Agent API",
    version=settings.app_version,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mokoa.co.ke"] if settings.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")
    start = time.monotonic()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)
    logger.info(
        "http.request",
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    structlog.contextvars.clear_contextvars()
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("http.unhandled_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


PREFIX = "/api/v1"
app.include_router(auth.router,            prefix=f"{PREFIX}/auth",         tags=["Auth"])
app.include_router(tills.router,           prefix=f"{PREFIX}/tills",        tags=["Tills"])
app.include_router(transactions.router,    prefix=f"{PREFIX}/transactions",  tags=["Transactions"])
app.include_router(daraja_webhooks.router, prefix=f"{PREFIX}/daraja",       tags=["Daraja Webhooks"])
app.include_router(agent.router,           prefix=f"{PREFIX}/agent",        tags=["Agent"])
app.include_router(sms.router,             prefix=f"{PREFIX}/sms",          tags=["SMS"])
app.include_router(telegram_router,        prefix="/telegram",              tags=["Telegram"])
app.include_router(miniapp_router, prefix="/api/v1/auth", tags=["Mini App Auth"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.app_version}
