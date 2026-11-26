"""LiveKit agent worker: entrypoint(ctx) runs one call."""

import asyncio
import importlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import find_dotenv, load_dotenv
from livekit.agents import AgentSession, JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.voice import room_io
from livekit.agents.worker import ServerEnvOption

from voice_agent.backend_client import BackendClient
from voice_agent.config import AgentSettings, get_settings
from voice_agent.lifecycle.shutdown import finalize_call
from voice_agent.lifecycle.summarizer import GeminiSummarizer
from voice_agent.lifecycle.transcript_recorder import TranscriptRecorder
from voice_agent.profile.prompt_composer import RuntimeContext
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.providers.noise import noise_selector
from voice_agent.providers.tts import build_hindi_tts
from voice_agent.providers.vad import load_vad
from voice_agent.session_factory import build_agent, build_session, speak
from voice_agent.telephony import dial_borrower
from voice_agent.tools.base import CallState, ToolContext
from voice_agent.tools.registry import build_tools

log = logging.getLogger("worker")
MAX_CONSECUTIVE_FAILURES = 3


def idle_processes() -> int | ServerEnvOption[int]:
    """Pre-warmed call processes kept ready (AGENT_IDLE_PROCESSES overrides). The framework's production default is
    one per CPU (up to 4), each holding its own copy of the models: on a 1 GB host that leaves no room for a live
    call, and the kernel kills call processes mid-conversation. One is enough to answer the next call instantly;
    a replacement is warmed as soon as it is taken. Dev mode keeps the framework's on-demand behaviour."""
    raw = os.environ.get("AGENT_IDLE_PROCESSES", "").strip()
    return int(raw) if raw else ServerEnvOption(dev_default=0, prod_default=1)


def preload_network() -> None:
    """Loads what the first backend request needs. Left to the first call, these imports and the TLS setup froze the
    agent's event loop for about 0.7s while the caller waited."""
    for module in ("httpcore._sync.connection", "anyio._backends._asyncio", "anyio._core._sockets"):
        importlib.import_module(module)
    httpx.AsyncClient()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = load_vad()
    preload_network()


@dataclass
class OpenCall:
    context: dict[str, Any]
    profile: AgentProfileSpec
    state: CallState
    session: AgentSession


async def open_call(ctx: Any, backend: Any, call_id: str, settings: AgentSettings, vad: Any) -> OpenCall:
    """Joins the room and prepares the call at the same time. The voice starts connecting as soon as it is known: a new
    connection to it takes about a second, which the caller otherwise hears as silence before the greeting."""

    async def prepare() -> OpenCall:
        context = await backend.get_context(call_id)  # profile snapshot + authorized runtime facts
        profile = AgentProfileSpec.model_validate(context["profile"])
        state = CallState(call_id=call_id, correlation_id=context["correlation_id"], direction=context["direction"])
        session: AgentSession = build_session(profile, settings, vad, userdata=state)
        if session.tts is not None:
            session.tts.prewarm()
        return OpenCall(context, profile, state, session)

    _, call = await asyncio.gather(ctx.connect(), prepare())
    return call


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
    call = await open_call(ctx, backend, call_id, settings, ctx.proc.userdata["vad"])
    step("call_opened")
    context, profile, state, session = call.context, call.profile, call.state, call.session
    rt = context["runtime"]
    runtime = RuntimeContext(direction=state.direction, now_iso=rt["now_utc"], timezone=rt["timezone"], call_id=call_id)

    tool_ctx = ToolContext(state=state, backend=backend)
    tool_ctx.session = session
    hindi_tts = (
        build_hindi_tts(settings, profile.voice_behavior.hindi_voice_id) if session.tts is not None else None
    )  # a realtime session speaks for itself
    agent = build_agent(profile, runtime, build_tools(profile.allowed_tools, tool_ctx), hindi_tts=hindi_tts)

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
        ctx.delete_room()  # disconnect the caller too, so both sides end together
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
            speak(session, lines["technical_difficulty"], interruptible=False)
            state.end_reason = state.end_reason or "provider_failure"
            session.shutdown(drain=True)
        else:
            speak(session, lines.get("temporary_issue", lines["not_understood"]))

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

    phone: str | None = None
    dial = context.get("dial")
    if dial:  # a real phone call: ring the borrower first; the session starts only once they have answered
        step("dialing")
        result = await dial_borrower(ctx.api, room=ctx.room.name, call_id=call_id, dial=dial)
        if not result.answered:
            state.end_reason = result.reason
            try:
                payload = {"reason": result.reason, "sip_status_code": result.sip_status_code}
                await backend.post_event(call_id, "dial_failed", payload)
            except Exception:
                log.exception("dial_failed event failed")
            closed.set()  # no session ran, so the shutdown hook need not wait for one to close
            ctx.delete_room()  # also disconnects the user's browser, if it was following the call
            ctx.shutdown(reason=result.reason or "dial_failed")
            return
        phone = result.identity
        step("answered")
        try:
            await backend.post_event(call_id, "answered")
        except Exception:
            log.exception("answered event failed")

    room_options = room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(noise_cancellation=noise_selector(settings)),
        close_on_disconnect=True,
    )
    if phone:  # listen to the borrower on the phone only, never to a browser following the call
        room_options.participant_identity = phone
    await session.start(agent=agent, room=ctx.room, room_options=room_options)
    step("session_started")
    try:
        await backend.post_event(call_id, "agent_joined")
    except Exception:
        log.exception("agent_joined event failed")

    greeting = profile.voice_behavior.greeting.strip()
    if greeting:
        speak(session, greeting)
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


# Consecutive failed attempts to reach LiveKit before the worker gives up. Once backed off they are 10s apart,
# so this is about a day. The framework's 16 (about 2.5 minutes) let a short internet outage shut the agent down.
MAX_RECONNECT_ATTEMPTS = 8640


def worker_options() -> WorkerOptions:
    return WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        agent_name=os.environ.get("AGENT_NAME", "voice-agent"),
        shutdown_process_timeout=60.0,  # summary generation must fit (default 10s is too short)
        num_idle_processes=idle_processes(),
        max_retry=MAX_RECONNECT_ATTEMPTS,
    )


def main() -> None:
    # The framework reads LIVEKIT_* from os.environ; export .env there (real env vars still win).
    load_dotenv(find_dotenv(usecwd=True), override=False)
    # LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET are read from the environment by the framework,
    # so `download-files` works at image build time without secrets.
    cli.run_app(worker_options())


if __name__ == "__main__":
    main()
