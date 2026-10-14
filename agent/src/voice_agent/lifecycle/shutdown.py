"""Shutdown hook: flush turns -> summary -> backend. Falls back to the backend summarizer on any failure."""

import asyncio
import logging
from typing import Any

from voice_agent.backend_client import BackendClient
from voice_agent.lifecycle.summarizer import summarize_with_timeout
from voice_agent.lifecycle.transcript_recorder import TranscriptRecorder
from voice_agent.tools.base import CallState

log = logging.getLogger("shutdown")


async def finalize_call(
    *,
    state: CallState,
    recorder: TranscriptRecorder,
    backend: BackendClient,
    generator: Any,
    model_version: str,
    closed: asyncio.Event,
    reason: str,
    timeout: float,
    extensions: dict[str, str] | None,
) -> None:
    try:
        await asyncio.wait_for(closed.wait(), 5)  # let the session emit its final items
    except TimeoutError:
        pass
    await recorder.flush()
    end_reason = state.end_reason or reason
    try:
        await backend.post_event(state.call_id, "session_closed", {"reason": end_reason})
    except Exception:
        log.exception("session_closed event failed")
    if not recorder.turns:
        await _fallback(backend, state)  # backend writes the "no conversation" summary
        return
    try:
        summary = await summarize_with_timeout(recorder.turns, generator, timeout, extensions=extensions)
        await backend.post_summary(
            state.call_id,
            {"status": "READY", "summary": summary, "model_version": model_version, "end_reason": end_reason},
        )
    except Exception:
        log.exception("agent-side summary failed; requesting backend fallback", extra={"call_id": state.call_id})
        await _fallback(backend, state)


async def _fallback(backend: BackendClient, state: CallState) -> None:
    try:
        await backend.request_fallback_summary(state.call_id)
    except Exception:
        log.exception("fallback request failed; sweeper will retry", extra={"call_id": state.call_id})
