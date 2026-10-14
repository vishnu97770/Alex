"""Backend safety net: summarize calls whose agent worker never delivered a summary."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Call, CallTurn
from app.services import summary_service
from app.services.context_prompt_generator import JsonGenerator

log = logging.getLogger("sweeper")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def sweep_once(
    s: AsyncSession,
    generator: JsonGenerator,
    model: str,
    *,
    now: datetime | None = None,
    grace: timedelta = timedelta(seconds=60),
    stale: timedelta = timedelta(minutes=30),
) -> int:
    """Returns number of calls handled. Ended calls wait `grace` for the worker; silent live calls
    older than `stale` are treated as a lost worker."""
    now = now or datetime.now(UTC)
    pending = (await s.scalars(select(Call).where(Call.summary_status == "PENDING"))).all()
    handled = 0
    for call in pending:
        last_turn = await s.scalar(select(func.max(CallTurn.created_at)).where(CallTurn.call_id == call.id))
        last_activity = _aware(last_turn or call.created_at)
        if call.ended_at is not None:
            due = _aware(call.ended_at) + grace <= now
        else:
            due = last_activity + stale <= now
            if due:
                call.ended_at, call.end_reason = now, "worker_lost"
        if not due:
            continue
        await summary_service.run_fallback(s, call.id, generator, model)
        handled += 1
    return handled


async def run_forever(
    sm: async_sessionmaker[AsyncSession], generator: JsonGenerator, model: str, interval: float = 30.0
) -> None:
    while True:
        try:
            async with sm() as s:
                await sweep_once(s, generator, model)
        except Exception:
            log.exception("sweep failed")
        await asyncio.sleep(interval)
