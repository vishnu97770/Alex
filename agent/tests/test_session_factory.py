"""Reusability proof: a different domain profile runs through the same factory with no code changes."""

from livekit.agents import AgentSession

from voice_agent.config import get_settings
from voice_agent.profile.prompt_composer import RuntimeContext
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.session_factory import build_agent, build_session, build_turn_handling
from voice_agent.tools.base import CallState, ToolContext
from voice_agent.tools.registry import build_tools

REMINDER = AgentProfileSpec.model_validate(
    {
        "identity": {"agent_name": "Remi", "role_summary": "appointment reminders"},
        "context_prompt": "Remind the patient of their appointment. Do nothing else.",
        "voice_behavior": {"latency_profile": "aggressive", "greeting": "Hi, this is Remi."},
    }
)


def test_latency_profiles_map_to_distinct_tuning():
    s = get_settings()
    ag = build_turn_handling(REMINDER, s, "vad")
    cons = build_turn_handling(
        REMINDER.model_copy(
            update={"voice_behavior": REMINDER.voice_behavior.model_copy(update={"latency_profile": "conservative"})}
        ),
        s,
        "vad",
    )
    assert ag["endpointing"]["min_delay"] < cons["endpointing"]["min_delay"]
    assert ag["preemptive_generation"]["enabled"] and not cons["preemptive_generation"]["enabled"]


async def test_second_profile_builds_real_session_and_agent():
    s = get_settings()
    state = CallState("c", "k")
    session = build_session(REMINDER, s, vad=None, userdata=state)
    assert isinstance(session, AgentSession)
    agent = build_agent(REMINDER, RuntimeContext("OUTBOUND", "now"), build_tools([], ToolContext(state, None)))
    assert "Remind the patient" in agent.instructions
