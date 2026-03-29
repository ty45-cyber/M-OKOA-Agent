"""
Domain Modes router — switch and query the user's active challenge area persona.
Drives agent behaviour and dashboard UX for each Money in Motion vertical.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db_session

router = APIRouter()

VALID_MODES = {'merchant', 'farmer', 'student', 'community', 'general'}

DOMAIN_DESCRIPTIONS = {
    'merchant': {
        'label': 'Merchant',
        'tagline': 'Lipa na M-Pesa reconciliation, automated.',
        'icon': '⬡',
        'color': '#00D664',
        'apis_used': ['Transaction Status', 'C2B', 'Account Balance'],
        'demo_prompt': 'Nionyeshe malipo ya leo na ile ambayo haijafanana na invoice',
    },
    'farmer': {
        'label': 'Farmer / Cooperative',
        'tagline': 'Instant crop payouts, zero middlemen.',
        'icon': '◈',
        'color': '#F5A623',
        'apis_used': ['B2C', 'Account Balance', 'Transaction Status'],
        'demo_prompt': 'Lipa Wanjiku KES 8,400 kwa mahindi 120kg @ 70 per kg',
    },
    'student': {
        'label': 'Student',
        'tagline': 'Fees paid directly to your institution.',
        'icon': '◻',
        'color': '#4D9EFF',
        'apis_used': ['STK Push', 'Bill Pay', 'Transaction Status'],
        'demo_prompt': 'Lipa fees KES 35,000 kwa University of Nairobi admission A001/2024',
    },
    'community': {
        'label': 'Chama / Community',
        'tagline': 'Real-time group wallet transparency.',
        'icon': '⬗',
        'color': '#9B59B6',
        'apis_used': ['Account Balance', 'C2B', 'B2C'],
        'demo_prompt': 'Nionyeshe taarifa ya Chama yetu — wangapi wamechanga mwezi huu?',
    },
    'general': {
        'label': 'General',
        'tagline': 'Full M-Pesa financial co-pilot.',
        'icon': '◎',
        'color': '#00D664',
        'apis_used': ['All Daraja APIs'],
        'demo_prompt': 'Uko na pesa ngapi kwa till zote?',
    },
}


class SetDomainModeRequest(BaseModel):
    mode: str


class DomainModeResponse(BaseModel):
    current_mode: str
    label: str
    tagline: str
    icon: str
    color: str
    apis_used: list[str]
    demo_prompt: str


@router.get(
    '/current',
    response_model=DomainModeResponse,
    summary='Get the current domain mode for this user',
)
async def get_domain_mode(current_user=Depends(get_current_user)):
    mode = getattr(current_user, 'domain_mode', 'general')
    info = DOMAIN_DESCRIPTIONS.get(mode, DOMAIN_DESCRIPTIONS['general'])
    return DomainModeResponse(current_mode=mode, **info)


@router.post(
    '/set',
    response_model=DomainModeResponse,
    summary='Switch to a Money in Motion challenge area',
)
async def set_domain_mode(
    payload: SetDomainModeRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from fastapi import HTTPException

    if payload.mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Choose from: {', '.join(VALID_MODES)}",
        )

    current_user.domain_mode = payload.mode
    await db.flush()

    info = DOMAIN_DESCRIPTIONS[payload.mode]
    return DomainModeResponse(current_mode=payload.mode, **info)


@router.get(
    '/all',
    summary='List all available domain modes with descriptions',
)
async def list_domain_modes():
    return [
        {'mode': mode, **info}
        for mode, info in DOMAIN_DESCRIPTIONS.items()
        if mode != 'general'
    ]