"""Typed settings. Fails fast at startup listing missing variable *names* only."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    internal_api_token: str = Field(min_length=16)
    workspace_cookie_secret: str = Field(min_length=16)
    app_origin: str = "http://localhost:5173"

    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    agent_name: str = "voice-agent"
    token_ttl_seconds: int = 600

    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-2.5-flash"

    transcript_retention_days: int = 90
    rate_limit_public: str = "30/minute"

    feature_outbound_panel: bool = False
    summary_webhook_url: str = ""
    summary_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        missing = sorted({str(err["loc"][0]).upper() for err in e.errors() if err["loc"]})
        raise ConfigError("Invalid or missing configuration variables: " + ", ".join(missing)) from None
