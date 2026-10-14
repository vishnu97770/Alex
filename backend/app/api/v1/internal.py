import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.agent_profiles import get_generator
from app.core.config import Settings, get_settings
from app.core.security import require_internal_token
from app.db.session import get_session
from app.schemas.call import EventIn, SummaryIn, TurnsIn
from app.services import call_service, summary_service
from app.services.context_prompt_generator import JsonGenerator

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_token)])


@router.get("/calls/{call_id}/context")
async def call_context(call_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    call = await call_service.get_call_any(session, call_id)
    return await call_service.runtime_context(session, call)


@router.post("/calls/{call_id}/turns")
async def post_turns(call_id: uuid.UUID, body: TurnsIn, session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    call = await call_service.get_call_any(session, call_id)
    n = await call_service.upsert_turns(session, call, [t.model_dump() for t in body.turns])
    return {"stored": n}


@router.post("/calls/{call_id}/events")
async def post_event(call_id: uuid.UUID, body: EventIn, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    call = await call_service.get_call_any(session, call_id)
    await call_service.apply_event(session, call, body.type, body.payload)
    return {"status": "ok"}


@router.post("/calls/{call_id}/summary")
async def post_summary(
    call_id: uuid.UUID, body: SummaryIn, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    call = await call_service.get_call_any(session, call_id)
    if body.status == "FAILED" or body.summary is None:
        await summary_service.mark_failed(session, call, body.error or "agent reported failure")
        return {"status": "FAILED"}
    await summary_service.store_summary(
        session, call, body.summary, model_version=body.model_version, end_reason=body.end_reason
    )
    return {"status": "READY"}


@router.post("/calls/{call_id}/summary/fallback")
async def summary_fallback(
    call_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    generator: JsonGenerator = Depends(get_generator),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    await summary_service.run_fallback(session, call_id, generator, settings.gemini_text_model)
    call = await call_service.get_call_any(session, call_id)
    return {"status": call.summary_status}
