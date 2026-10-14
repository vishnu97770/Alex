from livekit.agents import llm
from livekit.plugins import google

from voice_agent.config import AgentSettings


def build_llm(s: AgentSettings) -> llm.LLM:
    return google.LLM(model=s.agent_llm_model, api_key=s.gemini_api_key, temperature=s.llm_temperature)
