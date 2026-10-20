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

    # Real user auth (separate secret from the legacy anonymous workspace cookie).
    auth_jwt_secret: str = Field(min_length=16)
    access_token_ttl_seconds: int = 60 * 60 * 24 * 7
    rate_limit_auth: str = "10/minute"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""  # default: {APP_ORIGIN}/api/v1/auth/google/callback
    upload_dir: str = "uploads"
    avatar_max_bytes: int = 2 * 1024 * 1024

    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    agent_name: str = "voice-agent"
    token_ttl_seconds: int = 600

    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_models: str = "gemini-3.8-flash,gemini-3.5-flash"
    gemini_timeout_seconds: float = 20.0

    transcript_retention_days: int = 90
    rate_limit_public: str = "30/minute"

    feature_outbound_panel: bool = False
    summary_webhook_url: str = ""
    summary_webhook_secret: str = ""

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_redirect(self) -> str:
        return self.google_redirect_uri or f"{self.app_origin.rstrip('/')}/api/v1/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        missing = sorted({str(err["loc"][0]).upper() for err in e.errors() if err["loc"]})
        raise ConfigError("Invalid or missing configuration variables: " + ", ".join(missing)) from None
