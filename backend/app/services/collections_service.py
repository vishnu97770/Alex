import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict
from app.db.models import Agent, Call, CallLink, User
from app.schemas.collections import SoloCallIn
from app.services import agent_service, call_service, profile_service
from app.services.collections_prompt import BorrowerDetails, build_recovery_prompt, opening_line


def profile_fields(agent: Agent, borrower: BorrowerDetails | None) -> dict[str, object]:
    """What the worker reads from a call's profile: the agent's voice, the spoken opening and the call-ending
    conditions. Every call the agent places (individual or bulk) builds its profile here."""
    fields: dict[str, object] = {
        **agent_service.agent_fields(agent.name, agent.voice),
        "role_summary": "Loan recovery call",
        "conversation_flow": {"opening": opening_line(agent.name, borrower)},
    }
    if borrower is not None:  # what the Dashboard lists for the call; only the last 4 digits of the phone are kept
        fields["borrower"] = {
            "phone_last4": borrower.phone[-4:],
            "amount": f"{borrower.amount:.2f}",
            "currency": borrower.currency,
        }
    return fields


async def call_borrower(
    s: AsyncSession,
    settings: Settings,
    user: User,
    agent: Agent,
    borrower: BorrowerDetails,
    *,
    phone: bool,
) -> tuple[Call, str]:
    """The agent calls one borrower. The borrower's details live only in this call's own prompt snapshot (a profile
    nobody else uses); the call is linked to the agent so it shows as busy and is counted. `phone`: dial the
    borrower's real number through the SIP trunk; otherwise the user talks to the agent in the browser."""
    _, version = await profile_service.create_detached(
        s,
        user.workspace_id,
        source="loan-recovery-call",
        fields=profile_fields(agent, borrower),
        prompt=build_recovery_prompt(agent.name, borrower, voice=agent.voice),
        model="loan-recovery",
    )
    link = CallLink(call_id=uuid.uuid4(), uid=user.uid, agent_aid=agent.aid)
    if phone:
        return await call_service.create_phone_call(
            s, settings, user.workspace_id, version=version, link=link, dial_to=borrower.phone
        )
    return await call_service.create_web_call(s, settings, user.workspace_id, None, version=version, link=link)


async def start_solo_call(s: AsyncSession, settings: Settings, user: User, body: SoloCallIn) -> tuple[Call, str]:
    """Individual call: one borrower, made by the user's agent, in the browser or to the borrower's phone."""
    agent = await agent_service.get_active(s, user.uid)
    if agent is None:
        raise Conflict("Create your agent before placing calls.")
    phone = body.mode == "phone"
    if phone:
        if not settings.phone_calls_enabled:
            raise Conflict("Phone calls are not set up yet.")
        if await agent_service.is_busy(s, agent):
            raise Conflict("Your agent is already on a call. Try again when it has ended.")
    borrower = BorrowerDetails(
        name=body.borrower_name,
        phone=body.phone,
        amount=body.amount,
        bank=body.bank,
        currency=body.currency,
        due_date=body.due_date,
        notes=body.context,
    )
    return await call_borrower(s, settings, user, agent, borrower, phone=phone)
