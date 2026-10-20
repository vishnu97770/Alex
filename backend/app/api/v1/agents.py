import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_deps import get_user_for_uid
from app.db.models import Agent, User
from app.db.session import get_session
from app.schemas.account import AgentIn, AgentOut, PaymentIn
from app.services import agent_service

router = APIRouter(prefix="/users/{uid}/agents", tags=["agents"])


def _out(a: Agent, busy: bool = False) -> AgentOut:
    return AgentOut(
        aid=str(a.aid),
        name=a.name,
        role_behavior=a.role_behavior,
        status="busy" if busy else "free",
        lifecycle=a.lifecycle,
    )


@router.get("", response_model=list[AgentOut])
async def list_agents(
    user: User = Depends(get_user_for_uid), session: AsyncSession = Depends(get_session)
) -> list[AgentOut]:
    return [_out(a, busy) for a, busy in await agent_service.list_active(session, user.uid)]


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentIn, user: User = Depends(get_user_for_uid), session: AsyncSession = Depends(get_session)
) -> AgentOut:
    """Creates the agent as PENDING (hidden, unusable) so the payment step has an `aid` to work with."""
    return _out(await agent_service.create_pending(session, user, body.name, body.role_behavior))


@router.get("/{aid}", response_model=AgentOut)
async def get_agent(
    aid: uuid.UUID, user: User = Depends(get_user_for_uid), session: AsyncSession = Depends(get_session)
) -> AgentOut:
    a = await agent_service.get_owned(session, user.uid, aid)
    return _out(a, a.aid in await agent_service.busy_aids(session, user.uid))


@router.post("/{aid}/payment", response_model=AgentOut)
async def pay(
    aid: uuid.UUID,
    body: PaymentIn,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    """Simulated payment (no real gateway): an amount of exactly 100 activates the agent."""
    return _out(await agent_service.pay_and_activate(session, user, aid, body.amount))


@router.put("/{aid}", response_model=AgentOut)
async def update_agent(
    aid: uuid.UUID,
    body: AgentIn,
    user: User = Depends(get_user_for_uid),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    a = await agent_service.update(session, user, aid, body.name, body.role_behavior)
    return _out(a, a.aid in await agent_service.busy_aids(session, user.uid))
