"""
SMS router — receive forwarded M-Pesa SMS messages and return parsed results.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db_session
from app.models.sms_inbox import ParseStatus
from app.schemas.sms import SmsForwardRequest, SmsResponse, SmsParsedResult
from app.services.sms_service import SmsService
from pydantic import BaseModel

router = APIRouter()


class SmsIngestResponse(BaseModel):
    inbox: SmsResponse
    parsed: SmsParsedResult | None


class PaginatedSmsResponse(BaseModel):
    items: list[SmsResponse]
    total: int
    page: int
    page_size: int


@router.post(
    "/forward",
    response_model=SmsIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Forward an M-Pesa SMS for parsing and ledger import",
)
async def forward_sms(
    payload: SmsForwardRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    sms_service = SmsService(db)
    inbox_record, parsed = await sms_service.ingest_sms(
        user_id=current_user.id,
        payload=payload,
    )
    return SmsIngestResponse(
        inbox=SmsResponse.model_validate(inbox_record),
        parsed=parsed,
    )


@router.get(
    "/",
    response_model=PaginatedSmsResponse,
    summary="List SMS inbox with optional status filter",
)
async def list_sms_inbox(
    parse_status: ParseStatus | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    sms_service = SmsService(db)
    items, total = await sms_service.list_inbox(
        user_id=current_user.id,
        parse_status=parse_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedSmsResponse(
        items=[SmsResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )