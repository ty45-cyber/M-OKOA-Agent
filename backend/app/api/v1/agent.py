"""
Agent router — REST endpoint for web/PWA clients to interact with the agent.
Telegram bot uses AgentService directly, not this router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db_session
from app.models.agent_session import SessionSource
from app.services.agent_service import AgentService
from app.services.daraja_service import get_daraja_service

router = APIRouter()


class AgentMessageRequest(BaseModel):
    message: str
    conversation_history: list[dict] | None = None


class AgentMessageResponse(BaseModel):
    response: str
    session_public_id: str | None = None


def _get_agent_service(
    db: AsyncSession = Depends(get_db_session),
) -> AgentService:
    return AgentService(db, get_daraja_service())


@router.post(
    "/message",
    response_model=AgentMessageResponse,
    summary="Send a message to the M-Okoa Agent",
)
async def send_message(
    payload: AgentMessageRequest,
    current_user=Depends(get_current_user),
    agent_service: AgentService = Depends(_get_agent_service),
):
    from fastapi import HTTPException

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if len(payload.message) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Message too long. Maximum 2000 characters.",
        )

    response = await agent_service.handle_message(
        user_id=current_user.id,
        user_name=current_user.full_name,
        message_text=payload.message.strip(),
        session_source=SessionSource.web,
        conversation_history=payload.conversation_history,
    )

    return AgentMessageResponse(response=response)