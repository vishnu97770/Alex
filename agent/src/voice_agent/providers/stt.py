from livekit.agents import stt
from livekit.plugins import deepgram

from voice_agent.config import AgentSettings


def build_stt(s: AgentSettings) -> stt.STT:
    if s.stt_provider == "deepgram":
        return deepgram.STT(model=s.stt_model, interim_results=True, api_key=s.deepgram_api_key)
    raise ValueError(f"unsupported STT provider {s.stt_provider}")
