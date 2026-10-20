from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_deps import get_user_for_uid
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.db.models import ScreenTimeDaily, User
from app.db.session import get_session
from app.services.stats_service import _aware, resolve_tz

router = APIRouter(prefix="/users/{uid}/screen-time", tags=["screen-time"])

MAX_CREDIT = 60  # seconds credited per heartbeat, whatever the client claims
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class HeartbeatIn(BaseModel):
    seconds: int = Field(ge=1, le=MAX_CREDIT)
    tz: str | None = Field(default=None, max_length=64)


@router.post("/heartbeat", status_code=204)
@limiter.limit(lambda: get_settings().rate_limit_heartbeat)
async def heartbeat(
    request: Request,
    body: HeartbeatIn,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Credits foreground time to today (in the client's timezone), never more than the time actually elapsed."""
    now = datetime.now(UTC)
    day = now.astimezone(resolve_tz(body.tz)).date()
    row = await session.get(ScreenTimeDaily, (user.uid, day))
    if row is None:
        row = ScreenTimeDaily(uid=user.uid, day=day, seconds=0)
        session.add(row)
    credit = body.seconds
    if row.last_beat_at is not None:  # several tabs or a spammed endpoint cannot earn more than wall-clock time
        credit = min(credit, int((now - _aware(row.last_beat_at)).total_seconds()) + 2)
    row.seconds = (row.seconds or 0) + max(credit, 0)
    row.last_beat_at = now
    await session.commit()


@router.get("")
async def week(
    week_start: date | None = None,
    tz: str | None = None,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Hours per weekday for the week containing `week_start` (default: the current week, Monday first)."""
    today = datetime.now(UTC).astimezone(resolve_tz(tz)).date()
    anchor = week_start or today
    monday = anchor - timedelta(days=anchor.weekday())
    days = [monday + timedelta(days=i) for i in range(7)]
    rows = await session.scalars(
        select(ScreenTimeDaily).where(ScreenTimeDaily.uid == user.uid, ScreenTimeDaily.day.in_(days))
    )
    secs = {r.day: r.seconds for r in rows}
    return {
        "week_start": monday.isoformat(),
        "today": today.isoformat(),
        "days": [
            {"date": d.isoformat(), "weekday": WEEKDAYS[i], "hours": round(secs.get(d, 0) / 3600, 3)}
            for i, d in enumerate(days)
        ],
    }
