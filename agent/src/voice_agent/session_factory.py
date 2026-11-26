"""Builds an AgentSession from a profile + settings. Contains no domain logic."""

from typing import Any

from livekit.agents import AgentSession, tts
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.agents.voice.turn import TurnHandlingOptions

from voice_agent.bilingual import BilingualAgent
from voice_agent.config import AgentSettings
from voice_agent.profile.prompt_composer import RuntimeContext, compose_instructions
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.providers.live import build_realtime_model
from voice_agent.providers.llm import CALL_LLM_CONN_OPTIONS, build_llm
from voice_agent.providers.stt import build_stt
from voice_agent.providers.tts import build_tts
from voice_agent.providers.turn_detection import build_turn_detection
from voice_agent.session_profiles import LATENCY_PROFILES


def build_realtime_turn_handling(profile: AgentProfileSpec) -> TurnHandlingOptions:
    """Gemini Live detects the end of the caller's turn itself, so there is no endpointing to tune."""
    itr = profile.voice_behavior.interruption
    return TurnHandlingOptions(
        turn_detection="realtime_llm",
        interruption={"enabled": itr.enabled, "min_duration": itr.min_duration_s},
    )


def build_turn_handling(profile: AgentProfileSpec, settings: AgentSettings, turn_detection: Any) -> TurnHandlingOptions:
    tuning = LATENCY_PROFILES[profile.voice_behavior.latency_profile or settings.latency_profile]
    itr = profile.voice_behavior.interruption
    return TurnHandlingOptions(
        turn_detection=turn_detection,
        endpointing={
            # "dynamic" learns from pauses: one long silence raised the wait to 1.6s for the rest of the call.
            "mode": "fixed",
            "min_delay": tuning.endpoint_min_delay,
            "max_delay": tuning.endpoint_max_delay,
        },
        interruption={"enabled": itr.enabled, "min_duration": itr.min_duration_s, "min_words": itr.min_words},
        preemptive_generation={"enabled": tuning.preemptive_generation},
    )


def build_session(
    profile: AgentProfileSpec, settings: AgentSettings, vad: Any, *, userdata: Any = None
) -> AgentSession:
    kwargs: dict[str, Any] = {}
    if userdata is not None:
        kwargs["userdata"] = userdata
    if settings.agent_voice_mode == "realtime":
        return AgentSession(
            vad=vad, llm=build_realtime_model(settings), turn_handling=build_realtime_turn_handling(profile), **kwargs
        )
    return AgentSession(
        vad=vad,
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings, profile.voice_behavior.speaking_rate, profile.voice_behavior.voice_id),
        turn_handling=build_turn_handling(profile, settings, build_turn_detection(settings)),
        conn_options=SessionConnectOptions(llm_conn_options=CALL_LLM_CONN_OPTIONS),
        **kwargs,
    )


def build_agent(
    profile: AgentProfileSpec, runtime: RuntimeContext, tools: list[Any], *, hindi_tts: tts.TTS | None = None
) -> BilingualAgent:
    return BilingualAgent(instructions=compose_instructions(profile, runtime), tools=tools, hindi_tts=hindi_tts)


def speak(session: AgentSession, text: str, *, interruptible: bool = True) -> None:
    """Says `text`. A realtime session has no TTS, so the model is asked to say it in its own voice instead."""
    if session.tts is not None:
        session.say(text, allow_interruptions=interruptible)
    else:
        session.generate_reply(
            instructions=f'Say this to the caller now, naturally and without adding anything: "{text}"'
        )
