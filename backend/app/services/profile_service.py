import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.db.models import AgentProfile, AgentProfileVersion, Workspace
from app.services import audit_service
from app.services.context_prompt_generator import find_placeholders


async def _add_version(
    s: AsyncSession, profile: AgentProfile, *, source: str, fields: dict[str, Any], prompt: str, model: str
) -> AgentProfileVersion:
    v = AgentProfileVersion(
        profile_id=profile.id,
        workspace_id=profile.workspace_id,
        version=profile.current_version,
        source_description=source,
        structured_fields=fields,
        context_prompt=prompt,
        placeholders=find_placeholders(prompt),
        generator_model=model,
    )
    s.add(v)
    await s.flush()
    return v


async def create_and_activate(
    s: AsyncSession, workspace_id: uuid.UUID, *, source: str, fields: dict[str, Any], prompt: str, model: str
) -> tuple[AgentProfile, AgentProfileVersion]:
    p = AgentProfile(workspace_id=workspace_id, current_version=1)
    s.add(p)
    await s.flush()
    v = await _add_version(s, p, source=source, fields=fields, prompt=prompt, model=model)
    ws = await s.get(Workspace, workspace_id)
    assert ws is not None
    ws.active_profile_id = p.id
    await audit_service.record(
        s,
        "profile.created",
        actor="user",
        workspace_id=workspace_id,
        payload={"profile_id": str(p.id), "version": 1},
        model_versions={"generator": model},
    )
    await s.commit()
    return p, v


async def get_active(s: AsyncSession, workspace_id: uuid.UUID) -> tuple[AgentProfile, AgentProfileVersion]:
    ws = await s.get(Workspace, workspace_id)
    if ws is None or ws.active_profile_id is None:
        raise NotFound("No active agent profile")
    p = await s.get(AgentProfile, ws.active_profile_id)
    assert p is not None
    v = await s.scalar(
        select(AgentProfileVersion).where(
            AgentProfileVersion.profile_id == p.id, AgentProfileVersion.version == p.current_version
        )
    )
    assert v is not None
    return p, v


async def edit_prompt(
    s: AsyncSession, workspace_id: uuid.UUID, profile_id: uuid.UUID, prompt: str
) -> tuple[AgentProfile, AgentProfileVersion]:
    p = await s.get(AgentProfile, profile_id)
    if p is None or p.workspace_id != workspace_id:
        raise NotFound("Profile not found")
    prev = await s.scalar(
        select(AgentProfileVersion).where(
            AgentProfileVersion.profile_id == p.id, AgentProfileVersion.version == p.current_version
        )
    )
    assert prev is not None
    p.current_version += 1
    v = await _add_version(
        s, p, source=prev.source_description, fields=prev.structured_fields, prompt=prompt, model="user-edit"
    )
    ws = await s.get(Workspace, workspace_id)
    assert ws is not None
    ws.active_profile_id = p.id
    await audit_service.record(
        s,
        "profile.edited",
        actor="user",
        workspace_id=workspace_id,
        payload={"profile_id": str(p.id), "version": p.current_version},
    )
    await s.commit()
    return p, v
