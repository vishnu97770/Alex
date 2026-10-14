import logging
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_workspace_id, get_workspace_id
from app.core.config import Settings, get_settings
from app.core.ratelimit import limiter
from app.db.models import Call, CallSummary
from app.db.session import get_session
from app.schemas.call import CreateCallRequest, CreateCallResponse
from app.services import audit_service, call_service, livekit_service

log = logging.getLogger("calls")
router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("", response_model=CreateCallResponse)
@limiter.limit(lambda: get_settings().rate_limit_public)
async def create_call(
    request: Request,
    body: CreateCallRequest,
    workspace_id: uuid.UUID = Depends(get_workspace_id),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CreateCallResponse:
    call, token = await call_service.create_web_call(
        session, settings, workspace_id, uuid.UUID(body.profile_id) if body.profile_id else None
    )
    return CreateCallResponse(call_id=str(call.id), livekit_url=settings.livekit_url, token=token)


@router.get("")
async def list_calls(
    workspace_id: uuid.UUID | None = Depends(get_optional_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    if workspace_id is None:
        return []
    rows = (
        await session.scalars(
            select(Call).where(Call.workspace_id == workspace_id).order_by(Call.created_at.desc()).limit(200)
        )
    ).all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "status": c.state,
            "summary_status": c.summary_status,
            "started_at": c.started_at,
        }
        for c in rows
    ]


@router.get("/{call_id}")
async def get_call(
    call_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    call = await call_service.get_scoped_call(session, workspace_id, call_id)
    turns = await call_service.list_turns(session, call.id)
    summ = await session.scalar(select(CallSummary).where(CallSummary.call_id == call.id))
    return {
        "id": str(call.id),
        "title": call.title,
        "status": call.state,
        "summary_status": call.summary_status,
        "started_at": call.started_at,
        "ended_at": call.ended_at,
        "end_reason": call.end_reason,
        "turns": [{"seq": t.seq, "speaker": t.speaker, "text": t.text, "is_final": t.is_final} for t in turns],
        "summary": summ.summary_json if summ else None,
    }


@router.post("/{call_id}/end")
async def end_call(
    call_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace_id),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    call = await call_service.get_scoped_call(session, workspace_id, call_id)
    try:
        await livekit_service.close_room(settings, call.room_name)
    except Exception:  # room may already be gone; the agent shutdown still produces the summary
        log.warning("close_room failed", extra={"call_id": str(call.id)})
    await audit_service.record(
        session,
        "call.end_requested",
        actor="user",
        workspace_id=workspace_id,
        call_id=call.id,
        correlation_id=call.correlation_id,
    )
    await session.commit()
    return {"status": "ending"}
