"""
Mini App auth router — handles M-Pesa Super App identity exchange.
Called when a user opens the M-Okoa Mini App inside M-Pesa.

The auth_code from M-Pesa is exchanged for:
  1. A verified identity via Daraja 3.0 Security API
  2. An M-Okoa JWT for subsequent API calls
  3. A masked phone for display — never the raw MSISDN
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.user import User
from app.services.auth_service import AuthService, AuthError
from app.services.security_api_service import (
    SecurityAPIError,
    get_security_service,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


class MiniAppLoginRequest(BaseModel):
    auth_code: str


class MiniAppLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    masked_phone: str
    is_new_user: bool
    account_tier: str


@router.post(
    "/miniapp-login",
    response_model=MiniAppLoginResponse,
    summary="Exchange M-Pesa Mini App auth_code for M-Okoa session",
)
async def miniapp_login(
    payload: MiniAppLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    from fastapi import HTTPException
    from app.services.daraja_service import get_daraja_service

    security = get_security_service()
    daraja = get_daraja_service()

    # Step 1: Get Daraja OAuth token for Security API call
    # Uses a platform-level credential (not per-till)
    try:
        from app.core.config import get_settings
        import base64, httpx
        s = get_settings()
        raw = f"{s.daraja_platform_consumer_key}:{s.daraja_platform_consumer_secret}"
        encoded = base64.b64encode(raw.encode()).decode()
        async with httpx.AsyncClient() as client:
            token_res = await client.get(
                f"{s.daraja_base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {encoded}"},
            )
            access_token = token_res.json().get("access_token", "")
    except Exception as exc:
        logger.error("miniapp.oauth_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="M-Pesa service unavailable.")

    # Step 2: Resolve identity via Security API — no raw MSISDN
    try:
        identity = await security.resolve_miniapp_identity(
            auth_code=payload.auth_code,
            access_token=access_token,
        )
    except SecurityAPIError as exc:
        logger.warning("miniapp.identity_failed", error=str(exc))
        raise HTTPException(status_code=401, detail="Could not verify M-Pesa identity.")

    masked_phone = identity["masked_phone"]
    identity_token = identity["identity_token"]
    account_tier = identity["account_tier"]

    # Step 3: Find or create user by identity_token
    # identity_token is stable per user — we use it as the lookup key
    result = await db.execute(
        select(User).where(User.mpesa_identity_token == identity_token)
    )
    user = result.scalar_one_or_none()
    is_new_user = user is None

    if is_new_user:
        from ulid import ULID
        from app.core.security import hash_password
        import secrets

        # Create a new M-Okoa account from the Mini App
        # Phone is stored masked — raw MSISDN never touches our DB
        user = User(
            public_id=str(ULID()),
            full_name=f"M-Pesa User {masked_phone[-4:]}",
            phone_number=masked_phone,        # masked — e.g. 2547****5678
            password_hash=hash_password(secrets.token_urlsafe(32)),
            mpesa_identity_token=identity_token,
            is_active=True,
            is_verified=True,                 # Verified by M-Pesa KYC
        )
        db.add(user)
        await db.flush()

    logger.info(
        "miniapp.login",
        masked_phone=masked_phone,
        is_new=is_new_user,
        user_id=user.id,
    )

    from app.core.security import create_access_token, create_refresh_token
    return MiniAppLoginResponse(
        access_token=create_access_token(user.id, user.public_id),
        refresh_token=create_refresh_token(user.id),
        masked_phone=masked_phone,
        is_new_user=is_new_user,
        account_tier=account_tier,
    )