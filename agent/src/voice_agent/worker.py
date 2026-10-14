"""LiveKit agent worker: entrypoint(ctx) runs one call."""

import asyncio
import json
import logging
import os
import time

from dotenv import find_dotenv, load_dotenv
from livekit.agents import AgentSession, JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.voice import room_io

from voice_agent.backend_client import BackendClient
from voice_agent.config import get_settings
from voice_agent.lifecycle.shutdown import finalize_call
from voice_agent.lifecycle.summarizer import GeminiSummarizer
from voice_agent.lifecycle.transcript_recorder import TranscriptRecorder
from voice_agent.profile.prompt_composer import RuntimeContext
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.providers.noise import noise_selector
from voice_agent.providers.vad import load_vad
from voice_agent.session_factory import build_agent, build_session
from voice_agent.tools.base import CallState, ToolContext
from voice_agent.tools.registry import build_tools

log = logging.getLogger("worker")
MAX_CONSECUTIVE_FAILURES = 3


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = load_vad()


async def entrypoint(ctx: JobContext) -> None:
    t0 = time.perf_counter()

    def step(name: str) -> None:
        log.info("startup step", extra={"step": name, "elapsed_s": round(time.perf_counter() - t0, 2)})

    settings = get_settings()
    step("settings")
    meta = json.loads(ctx.job.metadata or "{}")
    call_id = meta.get("call_id")
    if not call_id:
        log.error("job has no call_id metadata; refusing to run")
        return
    ctx.log_context_fields = {"call_id": call_id, "correlation_id": meta.get("correlation_id", "")}
    backend = BackendClient(
        settings.backend_internal_url,
        settings.internal_api_token,
        correlation_id=meta.get("correlation_id", ""),
    )
    step("before_connect")
    await ctx.connect()
    step("connected")

    context = await backend.get_context(call_id)  # profile snapshot + authorized runtime facts
    step("context_fetched")
    profile = AgentProfileSpec.model_validate(context["profile"])
    rt = context["runtime"]
    state = CallState(call_id=call_id, correlation_id=context["correlation_id"], direction=context["direction"])
    runtime = RuntimeContext(direction=state.direction, now_iso=rt["now_utc"], timezone=rt["timezone"], call_id=call_id)

    tool_ctx = ToolContext(state=state, backend=backend)
    session: AgentSession = build_session(profile, settings, ctx.proc.userdata["vad"], userdata=state)
    tool_ctx.session = session
    agent = build_agent(profile, runtime, build_tools(profile.allowed_tools, tool_ctx))

    step("session_built")
    recorder = TranscriptRecorder(backend, call_id)
    recorder.attach(session)
    closed = asyncio.Event()
    unrecoverable = 0

    @session.on("close")
    def _on_close(ev: object) -> None:
        reason = getattr(ev, "reason", None)
        reason_s = str(getattr(reason, "value", reason) or "closed")
        state.end_reason = state.end_reason or reason_s
        closed.set()
        ctx.shutdown(reason=reason_s)  # run the shutdown hooks (summary) now, not when the room times out

    @session.on("error")
    def _on_error(ev: object) -> None:
        """Provider errors never hang up on the first failure: apologise and carry on; end the call only
        after MAX_CONSECUTIVE_FAILURES unrecoverable errors with no successful agent reply in between."""
        nonlocal unrecoverable
        err = getattr(ev, "error", None)
        if getattr(err, "recoverable", True):
            return
        unrecoverable += 1
        info = {"call_id": call_id, "consecutive": unrecoverable, "error_type": type(err).__name__}
        log.error("unrecoverable session error", extra=info)
        lines = profile.voice_behavior.fallback_lines
        if unrecoverable >= MAX_CONSECUTIVE_FAILURES:
            session.say(lines["technical_difficulty"], allow_interruptions=False)
            state.end_reason = state.end_reason or "provider_failure"
            session.shutdown(drain=True)
        else:
            session.say(lines.get("temporary_issue", lines["not_understood"]))

    @session.on("user_input_transcribed")
    def _on_user_text(ev: object) -> None:
        if getattr(ev, "is_final", False):
            state.user_turns += 1

    @session.on("agent_state_changed")
    def _on_agent_state(ev: object) -> None:
        nonlocal unrecoverable
        if getattr(ev, "new_state", None) == "speaking" and getattr(ev, "old_state", None) == "thinking":
            unrecoverable = 0  # a real LLM-backed reply got through

    @session.on("metrics_collected")
    def _on_metrics(ev: object) -> None:
        m = getattr(ev, "metrics", None)
        kind = getattr(m, "type", "")
        if kind == "llm_metrics":
            info = {"ttft": round(m.ttft, 3), "cancelled": m.cancelled, "tokens": m.total_tokens, "label": m.label}
        elif kind == "tts_metrics":
            info = {"ttfb": round(m.ttfb, 3), "cancelled": m.cancelled, "label": m.label}
        elif kind == "eou_metrics":
            info = {
                "eou_delay": round(m.end_of_utterance_delay, 3),
                "transcription_delay": round(m.transcription_delay, 3),
            }
        else:
            return
        log.info("metric %s", kind, extra={"call_id": call_id, **info})

    summarizer = GeminiSummarizer(settings)

    async def _on_shutdown(reason: str) -> None:
        await finalize_call(
            state=state,
            recorder=recorder,
            backend=backend,
            generator=summarizer,
            model_version=f"{settings.gemini_text_model}",
            closed=closed,
            reason=reason or "closed",
            timeout=settings.summary_timeout_seconds,
            extensions=profile.summary_schema_extensions or None,
        )
        await backend.aclose()

    ctx.add_shutdown_callback(_on_shutdown)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(noise_cancellation=noise_selector(settings)),
            close_on_disconnect=True,
        ),
    )
    step("session_started")
    try:
        await backend.post_event(call_id, "agent_joined")
    except Exception:
        log.exception("agent_joined event failed")

    greeting = profile.voice_behavior.greeting.strip()
    if greeting:
        session.say(greeting)
    else:
        session.generate_reply(instructions="Greet the caller briefly according to your role.")

    async def _limit() -> None:
        await asyncio.sleep(settings.max_call_seconds)
        state.end_reason = state.end_reason or "max_duration"
        session.shutdown(drain=True)

    limit_task = asyncio.create_task(_limit())
    ctx.add_shutdown_callback(lambda _reason=None: _cancel(limit_task))


async def _cancel(task: "asyncio.Task[None]") -> None:
    task.cancel()


def main() -> None:
    # The framework reads LIVEKIT_* from os.environ; export .env there (real env vars still win).
    load_dotenv(find_dotenv(usecwd=True), override=False)
    # LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET are read from the environment by the framework,
    # so `download-files` works at image build time without secrets.
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=os.environ.get("AGENT_NAME", "voice-agent"),
            shutdown_process_timeout=60.0,  # summary generation must fit (default 10s is too short)
        )
    )


if __name__ == "__main__":
    main()
