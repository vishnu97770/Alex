import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound, PaymentRejected
from app.db.models import Agent, AgentPayment, Call, CallLink, User
from app.services import audit_service, profile_service

PRICE = Decimal("100")
PENDING_TTL = timedelta(hours=24)
BUSY_WINDOW = timedelta(minutes=30)  # an unended call older than this is treated as a lost worker


def agent_prompt(name: str, role_behavior: str) -> str:
    return (
        f"You are {name}, a voice assistant on a phone-style call.\n\n"
        f"Your role and behaviour, as defined by your owner:\n{role_behavior}\n\n"
        "Keep replies short and natural for speech. Only state facts you were given; "
        "if you do not know something, say so."
    )


def agent_fields(name: str, role_behavior: str) -> dict[str, object]:
    return {
        "agent_name": name,
        "role_summary": role_behavior[:300],
        "conversation_flow": {"opening": f"Hi, this is {name}. How can I help?"},
        "escalation_rules": "",
        "call_ending_conditions": [],
        "assumptions_made": [],
    }


async def get_owned(s: AsyncSession, uid: uuid.UUID, aid: uuid.UUID) -> Agent:
    a = await s.get(Agent, aid)
    if a is None or a.uid != uid:  # same error for "missing" and "someone else's"
        raise NotFound("Agent not found")
    return a


async def busy_aids(s: AsyncSession, uid: uuid.UUID) -> set[uuid.UUID]:
    cutoff = datetime.now(UTC) - BUSY_WINDOW
    rows = await s.scalars(
        select(CallLink.agent_aid)
        .join(Call, Call.id == CallLink.call_id)
        .where(CallLink.uid == uid, CallLink.agent_aid.is_not(None), Call.ended_at.is_(None), Call.created_at > cutoff)
    )
    return {a for a in rows if a is not None}


async def list_active(s: AsyncSession, uid: uuid.UUID) -> list[tuple[Agent, bool]]:
    agents = (
        await s.scalars(select(Agent).where(Agent.uid == uid, Agent.lifecycle == "ACTIVE").order_by(Agent.created_at))
    ).all()
    busy = await busy_aids(s, uid)
    return [(a, a.aid in busy) for a in agents]


async def create_pending(s: AsyncSession, user: User, name: str, role_behavior: str) -> Agent:
    # abandoned, never-paid rows must not accumulate
    await s.execute(
        delete(Agent).where(
            Agent.uid == user.uid, Agent.lifecycle == "PENDING", Agent.created_at < datetime.now(UTC) - PENDING_TTL
        )
    )
    a = Agent(uid=user.uid, name=name, role_behavior=role_behavior, lifecycle="PENDING")
    s.add(a)
    await s.commit()
    return a


async def pay_and_activate(s: AsyncSession, user: User, aid: uuid.UUID, amount: Decimal) -> Agent:
    """Simulated payment: exactly 100 succeeds. No real gateway is involved."""
    a = await get_owned(s, user.uid, aid)
    if a.lifecycle == "ACTIVE":
        raise Conflict("Agent is already created")
    if amount != PRICE:
        s.add(AgentPayment(aid=a.aid, uid=user.uid, amount=amount, status="REJECTED"))
        await audit_service.record(
            s, "agent.payment_rejected", actor="user", workspace_id=user.workspace_id, payload={"aid": str(a.aid)}
        )
        await s.commit()
        raise PaymentRejected("Payment failed: please enter the exact amount (100).")
    p, _ = await profile_service.create_detached(
        s,
        user.workspace_id,
        source=a.role_behavior,
        fields=agent_fields(a.name, a.role_behavior),
        prompt=agent_prompt(a.name, a.role_behavior),
        model="user-defined",
    )
    a.lifecycle, a.profile_id = "ACTIVE", p.id
    s.add(AgentPayment(aid=a.aid, uid=user.uid, amount=amount, status="SUCCEEDED"))
    await audit_service.record(
        s, "agent.created", actor="user", workspace_id=user.workspace_id, payload={"aid": str(a.aid)}
    )
    await s.commit()
    return a


async def update(s: AsyncSession, user: User, aid: uuid.UUID, name: str, role_behavior: str) -> Agent:
    a = await get_owned(s, user.uid, aid)
    if a.lifecycle != "ACTIVE":
        raise NotFound("Agent not found")
    a.name, a.role_behavior = name, role_behavior
    if a.profile_id is not None:  # new immutable version; calls already made keep the old one
        await profile_service.append_version(
            s,
            a.profile_id,
            source=role_behavior,
            fields=agent_fields(name, role_behavior),
            prompt=agent_prompt(name, role_behavior),
            model="user-edit",
        )
    await audit_service.record(
        s, "agent.updated", actor="user", workspace_id=user.workspace_id, payload={"aid": str(a.aid)}
    )
    await s.commit()
    return a
