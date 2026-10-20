import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.correlation import new_correlation_id
from app.core.errors import NotFound
from app.core.state_machine import CALL, CallState
from app.db.models import AgentProfileVersion, Call, CallLink, CallTurn
from app.services import audit_service, livekit_service, profile_service


async def create_web_call(
    s: AsyncSession,
    settings: Settings,
    workspace_id: uuid.UUID,
    profile_id: uuid.UUID | None,
    *,
    version: AgentProfileVersion | None = None,
    link: CallLink | None = None,
) -> tuple[Call, str]:
    """`version`/`link` let the manager and agent calls pin a specific profile version and record ownership."""
    if profile_id is not None:
        raise NotFound("Selecting a non-active profile is not supported yet")
    if version is None:
        _, version = await profile_service.get_active(s, workspace_id)  # snapshot current version
    call = Call(
        workspace_id=workspace_id,
        direction="WEB",
        state=CallState.CREATED,
        room_name=livekit_service.new_room_name(),
        correlation_id=new_correlation_id(),
        profile_version_id=version.id,
        started_at=datetime.now(UTC),
    )
    s.add(call)
    await s.flush()
    if link is not None:
        link.call_id = call.id
        s.add(link)
    token = livekit_service.mint_participant_token(
        settings,
        room=call.room_name,
        identity=f"web-{call.id.hex[:12]}",
        call_id=call.id,
        correlation_id=call.correlation_id,
    )
    await audit_service.record(
        s,
        "call.created",
        actor="user",
        workspace_id=workspace_id,
        call_id=call.id,
        correlation_id=call.correlation_id,
        payload={"profile_version": version.version, "room": call.room_name},
    )
    await s.commit()
    return call, token


async def get_scoped_call(s: AsyncSession, workspace_id: uuid.UUID, call_id: uuid.UUID) -> Call:
    call = await s.get(Call, call_id)
    if call is None or call.workspace_id != workspace_id:
        raise NotFound("Call not found")
    return call


async def get_call_any(s: AsyncSession, call_id: uuid.UUID) -> Call:
    call = await s.get(Call, call_id)
    if call is None:
        raise NotFound("Call not found")
    return call


async def list_turns(s: AsyncSession, call_id: uuid.UUID) -> list[CallTurn]:
    return list((await s.scalars(select(CallTurn).where(CallTurn.call_id == call_id).order_by(CallTurn.seq))).all())


async def upsert_turns(s: AsyncSession, call: Call, turns: list[dict[str, Any]]) -> int:
    """Idempotent by (call_id, seq): duplicate / retried / out-of-order posts converge."""
    for t in turns:
        existing = await s.scalar(select(CallTurn).where(CallTurn.call_id == call.id, CallTurn.seq == t["seq"]))
        if existing is None:
            s.add(CallTurn(call_id=call.id, **t))
        else:
            for k, v in t.items():
                setattr(existing, k, v)
    await s.commit()
    return len(turns)


async def apply_event(s: AsyncSession, call: Call, event_type: str, payload: dict[str, Any]) -> None:
    if event_type == "agent_joined" and call.state == CallState.CREATED:
        call.state = CALL.check(CallState(call.state), CallState.ACTIVE)
    elif event_type == "session_closed":
        call.ended_at = call.ended_at or datetime.now(UTC)
        call.end_reason = call.end_reason or str(payload.get("reason", "closed"))[:60]
    await audit_service.record(
        s,
        f"call.{event_type}",
        actor="agent",
        workspace_id=call.workspace_id,
        call_id=call.id,
        correlation_id=call.correlation_id,
        payload=payload,
    )
    await s.commit()


async def runtime_context(s: AsyncSession, call: Call) -> dict[str, Any]:
    from app.services.profile_builder import build_generic_profile

    v = await s.get(AgentProfileVersion, call.profile_version_id)
    assert v is not None
    return {
        "call_id": str(call.id),
        "correlation_id": call.correlation_id,
        "direction": call.direction,
        "profile_version": v.version,
        "profile": build_generic_profile(v),
        "runtime": {"now_utc": datetime.now(UTC).isoformat(), "timezone": "UTC"},
    }
