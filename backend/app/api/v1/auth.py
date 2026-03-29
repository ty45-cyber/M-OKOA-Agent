"""
Auth router — registration, login, token refresh, Telegram binding.
All endpoints are rate-limited at the middleware layer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.auth import (
    BindTelegramRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserPublicProfile,
)
from app.services.auth_service import AuthError, AuthService

router = APIRouter()
bearer_scheme = HTTPBearer()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


def _get_auth_service(db: AsyncSession = Depends(get_db_session)) -> AuthService:
    return AuthService(db)


# ── Dependency: authenticated user ───────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_service: AuthService = Depends(_get_auth_service),
):
    try:
        return await auth_service.get_current_user(credentials.credentials)
    except AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ── Endpoints ────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new M-Okoa account",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(_get_auth_service),
):
    try:
        return await auth_service.register(payload, ip_address=_client_ip(request))
    except AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with phone number and password",
)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(_get_auth_service),
):
    try:
        return await auth_service.login(payload, ip_address=_client_ip(request))
    except AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange refresh token for a new access token",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    try:
        return await auth_service.refresh_access_token(payload.refresh_token)
    except AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post(
    "/bind-telegram",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Link a Telegram chat ID to the authenticated user",
)
async def bind_telegram(
    payload: BindTelegramRequest,
    request: Request,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(_get_auth_service),
):
    try:
        await auth_service.bind_telegram_chat(
            user_id=current_user.id,
            telegram_chat_id=payload.telegram_chat_id,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get(
    "/me",
    response_model=UserPublicProfile,
    summary="Get the authenticated user's profile",
)
async def get_me(current_user=Depends(get_current_user)):
    return UserPublicProfile(
        public_id=current_user.public_id,
        full_name=current_user.full_name,
        phone_number=current_user.phone_number,
        email=current_user.email,
        subscription_tier=current_user.subscription_tier,
        is_verified=current_user.is_verified,
    )
 