import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.core.state_machine import CALL, CallState
from app.db.models import Call, CallSummary, CallTurn
from app.services import audit_service
from app.services.context_prompt_generator import JsonGenerator

_CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"
if not _CONTRACTS.exists():  # container layout: /app/contracts
    _CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SUMMARY_SCHEMA: dict[str, Any] = json.loads((_CONTRACTS / "call-summary.schema.json").read_text())
SUMMARY_PROMPT = (_CONTRACTS / "summary_prompt.txt").read_text()


class InvalidSummary(AppError):
    status_code, code = 422, "invalid_summary"


def validate_summary(summary: dict[str, Any]) -> None:
    try:
        jsonschema.validate(summary, SUMMARY_SCHEMA)
    except jsonschema.ValidationError as e:
        raise InvalidSummary(f"summary does not match schema: {e.message[:200]}") from e


def format_transcript(turns: list[CallTurn]) -> str:
    return "\n".join(f"{t.speaker.upper()}: {t.text}" for t in turns if t.is_final)


async def store_summary(
    s: AsyncSession, call: Call, summary: dict[str, Any], *, model_version: str, end_reason: str | None
) -> None:
    validate_summary(summary)
    existing = await s.scalar(select(CallSummary).where(CallSummary.call_id == call.id))
    if existing:
        existing.summary_json, existing.model_version, existing.status = summary, model_version, "READY"
    else:
        s.add(CallSummary(call_id=call.id, summary_json=summary, model_version=model_version, status="READY"))
    call.title = summary["title"][:60]
    call.summary_status = "READY"
    if call.state in (CallState.CREATED, CallState.ACTIVE):
        call.state = CALL.check(CallState(call.state), CallState.COMPLETED)
    call.ended_at = call.ended_at or datetime.now(UTC)
    call.end_reason = call.end_reason or end_reason or summary.get("call_outcome")
    await audit_service.record(
        s,
        "call.summary_stored",
        actor="agent",
        workspace_id=call.workspace_id,
        call_id=call.id,
        correlation_id=call.correlation_id,
        model_versions={"summary": model_version},
    )
    await s.commit()


async def mark_failed(s: AsyncSession, call: Call, reason: str) -> None:
    call.summary_status = "FAILED"
    await audit_service.record(
        s,
        "call.summary_failed",
        actor="system",
        workspace_id=call.workspace_id,
        call_id=call.id,
        correlation_id=call.correlation_id,
        payload={"reason": reason[:200]},
    )
    await s.commit()


async def run_fallback(s: AsyncSession, call_id: uuid.UUID, generator: JsonGenerator, model: str) -> None:
    """Backend-side summary from persisted turns, for when the worker died first."""
    call = await s.get(Call, call_id)
    if call is None:
        raise NotFound("Call not found")
    if call.summary_status == "READY":
        return
    turns = list((await s.scalars(select(CallTurn).where(CallTurn.call_id == call_id).order_by(CallTurn.seq))).all())
    if not any(t.is_final for t in turns):
        summary = {
            "title": "Call with no conversation",
            "summary": "The call ended before any conversation took place.",
            "call_outcome": "abandoned",
            "key_points": [],
            "user_requests": [],
            "agent_commitments_and_next_actions": [],
            "unresolved_items": [],
            "information_collected": {},
            "sentiment": "unknown",
            "escalation_needed": False,
            "escalation_reason": None,
            "topics_outside_scope_raised": [],
            "confidence_notes": "No transcript turns were recorded.",
        }
        await store_summary(s, call, summary, model_version="none", end_reason="abandoned")
        return
    try:
        raw = await generator.generate_json(
            system=SUMMARY_PROMPT,
            user=f"<transcript>\n{format_transcript(turns)}\n</transcript>",
            schema=SUMMARY_SCHEMA,
            temperature=0.1,
        )
        await store_summary(s, call, raw, model_version="backend-fallback", end_reason=None)
    except AppError as e:
        await mark_failed(s, call, e.message)
