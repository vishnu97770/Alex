"""Agent runtime settings. Fails fast listing missing variable names (never values)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    pass


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    backend_internal_url: str = "http://localhost:8000"
    internal_api_token: str = Field(min_length=16)
    agent_name: str = "voice-agent"

    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str

    gemini_api_key: str
    agent_llm_model: str = "gemini-3.5-flash-lite"
    gemini_text_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_models: str = "gemini-3.8-flash,gemini-3.5-flash"  # summaries only
    # Live-call LLM fallbacks. Empty = flash-lite only: a failover chain waits out each model's attempt
    # timeout and then falls to slower models, which is what makes a call feel slow.
    agent_llm_fallback_models: str = ""
    llm_temperature: float = 0.3

    deepgram_api_key: str
    stt_provider: Literal["deepgram"] = "deepgram"
    tts_provider: Literal["deepgram"] = "deepgram"
    stt_model: str = "nova-3"
    tts_model: str = "aura-2-andromeda-en"

    latency_profile: Literal["aggressive", "balanced", "conservative"] = "balanced"
    turn_detection: Literal["semantic", "vad", "stt"] = "semantic"
    enable_noise_cancellation: bool = True

    max_call_seconds: int = 3600
    summary_timeout_seconds: float = 30.0
    log_level: str = "INFO"


@lru_cache
def get_settings() -> AgentSettings:
    try:
        return AgentSettings()  # type: ignore[call-arg]
    except ValidationError as e:
        missing = sorted({str(err["loc"][0]).upper() for err in e.errors() if err["loc"]})
        raise ConfigError("Invalid or missing configuration variables: " + ", ".join(missing)) from None
