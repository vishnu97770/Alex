"""Append-only audit log. Only `record` exists: there is deliberately no update/delete."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.correlation import get_correlation_id
from app.db.models import AuditEvent


async def record(
    session: AsyncSession,
    event_type: str,
    *,
    actor: str,
    workspace_id: uuid.UUID | None = None,
    call_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
    correlation_id: str | None = None,
    payload: dict[str, Any] | None = None,
    model_versions: dict[str, str] | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        correlation_id=correlation_id or get_correlation_id(),
        workspace_id=workspace_id,
        call_id=call_id,
        application_id=application_id,
        actor=actor,
        event_type=event_type,
        payload=payload or {},
        model_versions=model_versions or {},
    )
    session.add(ev)
    await session.flush()
    return ev
