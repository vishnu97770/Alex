import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_deps import get_user_for_uid
from app.db.models import User
from app.db.session import get_session
from app.services import agent_service, stats_service
from app.services.stats_service import Metric, Range

router = APIRouter(prefix="/users/{uid}/stats", tags=["stats"])


@router.get("/usage")
async def usage(
    metric: Metric,
    range: Range,
    agent_id: uuid.UUID | None = None,
    tz: str | None = None,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """One series per agent (plus the manager) with zero-filled buckets; `agent_id` narrows it to one owned agent."""
    zone = stats_service.resolve_tz(tz)
    agent = await agent_service.get_owned(session, user.uid, agent_id) if agent_id else None
    return await stats_service.usage(session, user.uid, metric, range, zone, agent)
