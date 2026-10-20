import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.errors import Conflict
from app.db.models import Agent, User, Workspace
from app.services import audit_service, manager_service


async def get_by_email(s: AsyncSession, email: str) -> User | None:
    return await s.scalar(select(User).where(User.email == email.lower()))


async def create_user(
    s: AsyncSession,
    *,
    username: str,
    email: str,
    password: str | None = None,
    google_sub: str | None = None,
) -> User:
    """Creates the user, their (new, empty) workspace and their manager in one transaction."""
    if await get_by_email(s, email) is not None:
        raise Conflict("An account with this email already exists")
    ws = Workspace()
    s.add(ws)
    await s.flush()
    user = User(
        uid=uuid.uuid4(),
        username=username,
        email=email.lower(),
        password_hash=hash_password(password) if password else None,
        google_sub=google_sub,
        workspace_id=ws.id,
    )
    s.add(user)
    await s.flush()
    await manager_service.ensure_manager(s, user)
    await audit_service.record(
        s,
        "user.registered",
        actor="user",
        workspace_id=ws.id,
        payload={"uid": str(user.uid), "provider": "google" if google_sub else "password"},
    )
    await s.commit()
    return user


async def agent_count(s: AsyncSession, uid: uuid.UUID) -> int:
    return int(
        await s.scalar(select(func.count()).select_from(Agent).where(Agent.uid == uid, Agent.lifecycle == "ACTIVE"))
        or 0
    )


def avatar_url(user: User) -> str | None:
    if not user.avatar_path:
        return None
    stamp = int(user.avatar_updated_at.timestamp()) if user.avatar_updated_at else 0
    return f"/api/v1/users/{user.uid}/avatar?v={stamp}"


def username_from_email(email: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]", "", email.split("@")[0])[:40] or "user"
