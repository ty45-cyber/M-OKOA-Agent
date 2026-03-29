"""
Tills router — CRUD for M-Pesa tills, balance queries, smart float rules.
All endpoints require authentication.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db_session
from app.schemas.till import (
    BalanceResponse,
    SmartFloatRuleRequest,
    SmartFloatRuleResponse,
    TillCreateRequest,
    TillResponse,
    TillUpdateRequest,
)
from app.services.daraja_service import get_daraja_service
from app.services.till_service import TillError, TillService

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


def _get_till_service(
    db: AsyncSession = Depends(get_db_session),
) -> TillService:
    return TillService(db, get_daraja_service())


def _http_error(exc: TillError):
    from fastapi import HTTPException
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


# ── Endpoints ────────────────────────────────────────────────

@router.post(
    "/",
    response_model=TillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new M-Pesa Till or Paybill",
)
async def add_till(
    payload: TillCreateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    try:
        return await till_service.add_till(current_user, payload, _client_ip(request))
    except TillError as exc:
        _http_error(exc)


@router.get(
    "/",
    response_model=list[TillResponse],
    summary="List all active tills for the authenticated user",
)
async def list_tills(
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    return await till_service.list_tills(current_user.id)


@router.get(
    "/{till_public_id}",
    response_model=TillResponse,
    summary="Get a single till by public ID",
)
async def get_till(
    till_public_id: str,
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    try:
        till = await till_service.get_till(current_user.id, till_public_id)
        return TillResponse.model_validate(till)
    except TillError as exc:
        _http_error(exc)


@router.patch(
    "/{till_public_id}",
    response_model=TillResponse,
    summary="Update till details or Daraja credentials",
)
async def update_till(
    till_public_id: str,
    payload: TillUpdateRequest,
    request: Request,
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    try:
        return await till_service.update_till(
            current_user, till_public_id, payload, _client_ip(request)
        )
    except TillError as exc:
        _http_error(exc)


@router.delete(
    "/{till_public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a till (soft delete)",
)
async def deactivate_till(
    till_public_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    try:
        await till_service.deactivate_till(
            current_user, till_public_id, _client_ip(request)
        )
    except TillError as exc:
        _http_error(exc)


@router.get(
    "/{till_public_id}/balance",
    response_model=BalanceResponse,
    summary="Query current M-Pesa balance for a till",
)
async def query_balance(
    till_public_id: str,
    force_refresh: bool = False,
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    try:
        return await till_service.query_balance(
            current_user, till_public_id, force_refresh
        )
    except TillError as exc:
        _http_error(exc)


@router.get(
    "/balances/all",
    response_model=list[BalanceResponse],
    summary="Aggregate balance across all tills — 'Pesa ngapi kwa till zote?'",
)
async def aggregate_balances(
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    return await till_service.aggregate_all_balances(current_user)


@router.post(
    "/{till_public_id}/smart-float-rules",
    response_model=SmartFloatRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a Smart Float automation rule to a till",
)
async def add_smart_float_rule(
    till_public_id: str,
    payload: SmartFloatRuleRequest,
    request: Request,
    current_user=Depends(get_current_user),
    till_service: TillService = Depends(_get_till_service),
):
    try:
        return await till_service.add_smart_float_rule(
            current_user, till_public_id, payload, _client_ip(request)
        )
    except TillError as exc:
        _http_error(exc)
