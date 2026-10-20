from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_deps import get_user_for_uid
from app.core.config import Settings, get_settings
from app.core.ratelimit import limiter
from app.db.models import User
from app.db.session import get_session
from app.schemas.account import ManagerOut
from app.schemas.call import CreateCallResponse
from app.services import manager_service

router = APIRouter(prefix="/users/{uid}/manager", tags=["manager"])


@router.get("", response_model=ManagerOut)
async def get_manager(
    user: User = Depends(get_user_for_uid), session: AsyncSession = Depends(get_session)
) -> ManagerOut:
    m = await manager_service.ensure_manager(session, user)
    await session.commit()
    return ManagerOut(mid=str(m.mid), uid=str(user.uid))


@router.get("/calls")
async def list_manager_calls(
    user: User = Depends(get_user_for_uid), session: AsyncSession = Depends(get_session)
) -> list[dict[str, object]]:
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "status": c.state,
            "summary_status": c.summary_status,
            "started_at": c.started_at,
        }
        for c in await manager_service.list_calls(session, user.uid)
    ]


@router.post("/calls", response_model=CreateCallResponse)
@limiter.limit(lambda: get_settings().rate_limit_public)
async def start_manager_call(
    request: Request,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CreateCallResponse:
    call, token = await manager_service.start_call(session, settings, user)
    return CreateCallResponse(call_id=str(call.id), livekit_url=settings.livekit_url, token=token)
