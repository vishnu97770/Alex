from livekit.agents import llm
from livekit.plugins import google

from voice_agent.config import AgentSettings

# Gemini rejects request deadlines under 10s with HTTP 400 (found the hard way), so never go below this.
ATTEMPT_TIMEOUT_S = 15.0


def model_chain(primary: str, fallbacks: str) -> list[str]:
    return list(dict.fromkeys([primary, *[m.strip() for m in fallbacks.split(",") if m.strip()]]))


def build_llm(s: AgentSettings) -> llm.LLM:
    """Primary model with automatic failover: Gemini overload (503) must not drop a live call."""
    llms = [
        google.LLM(model=m, api_key=s.gemini_api_key, temperature=s.llm_temperature)
        for m in model_chain(s.agent_llm_model, s.gemini_fallback_models)
    ]
    return (
        llms[0] if len(llms) == 1 else llm.FallbackAdapter(llms, attempt_timeout=ATTEMPT_TIMEOUT_S, max_retry_per_llm=0)
    )
