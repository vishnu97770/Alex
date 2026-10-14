"""LiveKit agent worker: entrypoint(ctx) runs one call."""

import asyncio
import json
import logging
import os

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


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = load_vad()


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
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
    await ctx.connect()

    context = await backend.get_context(call_id)  # profile snapshot + authorized runtime facts
    profile = AgentProfileSpec.model_validate(context["profile"])
    rt = context["runtime"]
    state = CallState(call_id=call_id, correlation_id=context["correlation_id"], direction=context["direction"])
    runtime = RuntimeContext(direction=state.direction, now_iso=rt["now_utc"], timezone=rt["timezone"], call_id=call_id)

    tool_ctx = ToolContext(state=state, backend=backend)
    session: AgentSession = build_session(profile, settings, ctx.proc.userdata["vad"], userdata=state)
    tool_ctx.session = session
    agent = build_agent(profile, runtime, build_tools(profile.allowed_tools, tool_ctx))

    recorder = TranscriptRecorder(backend, call_id)
    recorder.attach(session)
    closed = asyncio.Event()
    unrecoverable = 0

    @session.on("close")
    def _on_close(_: object) -> None:
        closed.set()

    @session.on("error")
    def _on_error(ev: object) -> None:
        nonlocal unrecoverable
        err = getattr(ev, "error", None)
        if getattr(err, "recoverable", True):
            return
        unrecoverable += 1
        log.error(
            "unrecoverable session error",
            extra={"call_id": call_id, "source": type(getattr(ev, "source", "")).__name__},
        )
        if unrecoverable == 1:
            session.say(profile.voice_behavior.fallback_lines["technical_difficulty"], allow_interruptions=False)
        state.end_reason = state.end_reason or "provider_failure"
        session.shutdown(drain=True)

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
