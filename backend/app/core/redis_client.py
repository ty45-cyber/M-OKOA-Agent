"""
Redis client — agent state, STK correlation, rate limiting, token cache.
Single pool shared across the application.
"""
import redis.asyncio as aioredis
from app.core.config import get_settings
import structlog

logger = structlog.get_logger(__name__)
settings = get_settings()

# Module-level pool — initialised at startup via lifespan
_redis_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis_pool
    _redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await _redis_pool.ping()
    logger.info("redis.connected", url=settings.redis_url)


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        logger.info("redis.disconnected")


def get_redis() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialised. Call init_redis() first.")
    return _redis_pool


# ── Key namespacing ──────────────────────────────────────────
class RedisKeys:
    """Centralised key builder — no raw strings scattered in business logic."""

    @staticmethod
    def daraja_token(shortcode: str) -> str:
        return f"daraja:token:{shortcode}"

    @staticmethod
    def stk_session(checkout_request_id: str) -> str:
        return f"stk:session:{checkout_request_id}"

    @staticmethod
    def agent_state(session_id: str) -> str:
        return f"agent:state:{session_id}"

    @staticmethod
    def rate_limit(user_id: int, action: str) -> str:
        return f"ratelimit:{user_id}:{action}"

    @staticmethod
    def till_balance_cache(till_id: int) -> str:
        return f"till:balance:{till_id}"