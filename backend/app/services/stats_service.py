import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import Agent, Call, CallLink

Metric = Literal["calls", "minutes"]
Range = Literal["today", "7d", "28d"]
DAYS = {"7d": 7, "28d": 28}
MAX_CALL_MINUTES = 120  # a call longer than this counts as this much (a lost worker never sets ended_at cleanly)


class BadTimezone(AppError):
    status_code, code = 422, "bad_timezone"


def resolve_tz(name: str | None) -> ZoneInfo:
    """The client's IANA timezone (users have no stored timezone); UTC when absent."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise BadTimezone("Unknown timezone") from None


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)  # SQLite hands back naive UTC


def buckets(range_: Range, tz: ZoneInfo, now: datetime | None = None) -> list[datetime]:
    """Bucket start instants in `tz`: 24 hours for `today`, otherwise one per day ending today."""
    local = (now or datetime.now(UTC)).astimezone(tz)
    midnight = datetime.combine(local.date(), time.min, tzinfo=tz)
    if range_ == "today":
        return [midnight + timedelta(hours=h) for h in range(24)]
    return [
        datetime.combine(local.date() - timedelta(days=i), time.min, tzinfo=tz) for i in range(DAYS[range_] - 1, -1, -1)
    ]


def _index(at: datetime, starts: list[datetime], range_: Range, tz: ZoneInfo) -> int | None:
    local = _aware(at).astimezone(tz)
    if range_ == "today":
        first = starts[0]
        return local.hour if local.date() == first.date() else None
    d: date = local.date()
    for i, s in enumerate(starts):
        if s.date() == d:
            return i
    return None


def _value(call: Call, metric: Metric) -> float | None:
    if metric == "calls":
        return 1.0
    if call.started_at is None or call.ended_at is None:  # unended calls are excluded, never counted as infinite
        return None
    secs = (_aware(call.ended_at) - _aware(call.started_at)).total_seconds()
    return min(max(secs, 0.0), MAX_CALL_MINUTES * 60) / 60


async def usage(
    s: AsyncSession, uid: uuid.UUID, metric: Metric, range_: Range, tz: ZoneInfo, agent: Agent | None
) -> dict[str, object]:
    starts = buckets(range_, tz)
    rows = (
        await s.execute(
            select(Call, CallLink)
            .join(CallLink, CallLink.call_id == Call.id)
            .where(CallLink.uid == uid, Call.created_at >= starts[0].astimezone(UTC) - timedelta(days=1))
        )
    ).all()
    sums: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(starts))
    for call, link in rows:
        key = str(link.agent_aid) if link.agent_aid else "manager" if link.manager_mid else None
        if key is None or (agent is not None and key != str(agent.aid)):
            continue
        v = _value(call, metric)
        i = _index(call.started_at or call.created_at, starts, range_, tz)
        if v is not None and i is not None:
            sums[key][i] += v
    if agent is not None:
        series = [{"id": str(agent.aid), "name": agent.name, "kind": "agent"}]
    else:
        q = select(Agent).where(Agent.uid == uid, Agent.lifecycle == "ACTIVE").order_by(Agent.created_at)
        series = [{"id": str(a.aid), "name": a.name, "kind": "agent"} for a in (await s.scalars(q)).all()]
        series.append({"id": "manager", "name": "Manager", "kind": "manager"})
    zeros = [0.0] * len(starts)
    for item in series:
        vals = sums.get(str(item["id"]), zeros)
        item["points"] = [round(x, 1) if metric == "minutes" else int(x) for x in vals]  # type: ignore[assignment]
    return {
        "metric": metric,
        "range": range_,
        "tz": tz.key,
        "buckets": [b.isoformat() for b in starts],
        "series": series,
    }
