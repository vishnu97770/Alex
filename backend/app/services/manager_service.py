import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Call, CallLink, Manager, User
from app.services import call_service, profile_service

BASE_PROMPT = (
    "You are the user's Manager: a voice assistant that knows about all of the agents they have created.\n"
    "Answer questions about their agents using ONLY the information below: which agents exist, what each is for, "
    "and which are busy (on a call) or free right now.\n"
    "You do not yet have data about what each agent has done today. If asked, say that information is not "
    "available yet. Never invent agents, calls or activity.\n"
    "Keep replies short and natural for speech."
)


def manager_prompt(username: str, agents: list[tuple[str, str, bool]]) -> str:
    if agents:
        lines = "\n".join(
            f"- {name}: {'busy (on a call)' if busy else 'free'}. Role: {role}" for name, role, busy in agents
        )
    else:
        lines = "(The user has no agents yet.)"
    return f"{BASE_PROMPT}\n\nThe user's name is {username}.\n\nTheir agents right now:\n{lines}"


def _fields(username: str) -> dict[str, object]:
    return {
        "agent_name": "Manager",
        "role_summary": f"Manager voice agent for {username}'s agents",
        "conversation_flow": {"opening": f"Hi {username}, I'm your manager. How can I help with your agents?"},
        "escalation_rules": "",
        "call_ending_conditions": [],
        "assumptions_made": [],
    }


async def ensure_manager(s: AsyncSession, user: User) -> Manager:
    """One manager per user; created with the account, or lazily for accounts that predate it. Caller commits."""
    m = await s.scalar(select(Manager).where(Manager.uid == user.uid))
    if m is None:
        m = Manager(uid=user.uid)
        s.add(m)
        await s.flush()
    if m.profile_id is None:
        p, _ = await profile_service.create_detached(
            s,
            user.workspace_id,
            source="manager",
            fields=_fields(user.username),
            prompt=manager_prompt(user.username, []),
            model="manager",
        )
        m.profile_id = p.id
        await s.flush()
    return m


async def start_call(s: AsyncSession, settings: Settings, user: User) -> tuple[Call, str]:
    from app.services import agent_service

    m = await ensure_manager(s, user)
    assert m.profile_id is not None
    agents = [(a.name, a.role_behavior, busy) for a, busy in await agent_service.list_active(s, user.uid)]
    prompt = manager_prompt(user.username, agents)
    version = await profile_service.current_version(s, m.profile_id)
    if version.context_prompt != prompt:  # snapshot fresh agent info; only add a version when it changed
        version = await profile_service.append_version(
            s, m.profile_id, source="manager", fields=_fields(user.username), prompt=prompt, model="manager"
        )
    return await call_service.create_web_call(
        s,
        settings,
        user.workspace_id,
        None,
        version=version,
        link=CallLink(call_id=uuid.uuid4(), uid=user.uid, manager_mid=m.mid),
    )


async def list_calls(s: AsyncSession, uid: uuid.UUID) -> list[Call]:
    return list(
        (
            await s.scalars(
                select(Call)
                .join(CallLink, CallLink.call_id == Call.id)
                .where(CallLink.uid == uid, CallLink.manager_mid.is_not(None))
                .order_by(Call.created_at.desc())
                .limit(200)
            )
        ).all()
    )
