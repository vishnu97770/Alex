from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateCallRequest(BaseModel):
    profile_id: str | None = None


class CreateCallResponse(BaseModel):
    call_id: str
    livekit_url: str
    token: str


class TurnIn(BaseModel):
    seq: int = Field(ge=0)
    speaker: str = Field(pattern="^(user|agent)$")
    text: str = Field(max_length=8000)
    is_final: bool = True
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metrics_json: dict[str, Any] = {}


class TurnsIn(BaseModel):
    turns: list[TurnIn] = Field(max_length=200)


class EventIn(BaseModel):
    type: str = Field(pattern="^[a-z_]{1,40}$")
    payload: dict[str, Any] = {}


class SummaryIn(BaseModel):
    status: str = Field(default="READY", pattern="^(READY|FAILED)$")
    summary: dict[str, Any] | None = None
    model_version: str = ""
    end_reason: str | None = None
    error: str | None = None
