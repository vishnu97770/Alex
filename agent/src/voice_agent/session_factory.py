"""Builds an AgentSession from a profile + settings. Contains no domain logic."""

from typing import Any

from livekit.agents import Agent, AgentSession
from livekit.agents.voice.turn import TurnHandlingOptions

from voice_agent.config import AgentSettings
from voice_agent.profile.prompt_composer import RuntimeContext, compose_instructions
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.providers.llm import build_llm
from voice_agent.providers.stt import build_stt
from voice_agent.providers.tts import build_tts
from voice_agent.providers.turn_detection import build_turn_detection
from voice_agent.session_profiles import LATENCY_PROFILES


def build_turn_handling(profile: AgentProfileSpec, settings: AgentSettings, turn_detection: Any) -> TurnHandlingOptions:
    tuning = LATENCY_PROFILES[profile.voice_behavior.latency_profile or settings.latency_profile]
    itr = profile.voice_behavior.interruption
    return TurnHandlingOptions(
        turn_detection=turn_detection,
        endpointing={
            "mode": "dynamic",
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
    return AgentSession(
        vad=vad,
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings, profile.voice_behavior.speaking_rate),
        turn_handling=build_turn_handling(profile, settings, build_turn_detection(settings)),
        **kwargs,
    )


def build_agent(profile: AgentProfileSpec, runtime: RuntimeContext, tools: list[Any]) -> Agent:
    return Agent(instructions=compose_instructions(profile, runtime), tools=tools)
