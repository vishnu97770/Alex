import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_workspace_id, get_workspace_id
from app.core.config import get_settings
from app.core.errors import NotFound
from app.core.ratelimit import limiter
from app.db.models import AgentProfile, AgentProfileVersion
from app.db.session import get_session
from app.schemas.profile import GenerateProfileRequest, ProfileOut, UpdateProfileRequest
from app.services import profile_service
from app.services.context_prompt_generator import JsonGenerator, generate_context_prompt

router = APIRouter(prefix="/agent-profiles", tags=["agent-profiles"])


def get_generator() -> JsonGenerator:
    from app.services.context_prompt_generator import GeminiJsonGenerator

    return GeminiJsonGenerator()


def _out(p: AgentProfile, v: AgentProfileVersion) -> ProfileOut:
    return ProfileOut(
        profile_id=str(p.id),
        version=v.version,
        context_prompt=v.context_prompt,
        structured_fields=v.structured_fields,
        placeholders=list(v.placeholders),
        assumptions_made=list(v.structured_fields.get("assumptions_made", [])),
    )


@router.post("/generate", response_model=ProfileOut)
@limiter.limit(lambda: get_settings().rate_limit_public)
async def generate(
    request: Request,
    body: GenerateProfileRequest,
    workspace_id: uuid.UUID = Depends(get_workspace_id),
    session: AsyncSession = Depends(get_session),
    generator: JsonGenerator = Depends(get_generator),
) -> ProfileOut:
    fields, prompt, _ = await generate_context_prompt(body.description, generator)
    model = getattr(generator, "model", "unknown")
    p, v = await profile_service.create_and_activate(
        session, workspace_id, source=body.description, fields=fields.model_dump(), prompt=prompt, model=model
    )
    return _out(p, v)


@router.get("/active", response_model=ProfileOut)
async def active(
    workspace_id: uuid.UUID | None = Depends(get_optional_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    if workspace_id is None:
        raise NotFound("No active agent profile")
    p, v = await profile_service.get_active(session, workspace_id)
    return _out(p, v)


@router.put("/{profile_id}", response_model=ProfileOut)
async def update(
    profile_id: uuid.UUID,
    body: UpdateProfileRequest,
    workspace_id: uuid.UUID = Depends(get_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    p, v = await profile_service.edit_prompt(session, workspace_id, profile_id, body.context_prompt)
    return _out(p, v)
