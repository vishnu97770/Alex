import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedMixin, IdMixin, JsonType


class Workspace(Base, IdMixin, CreatedMixin):
    __tablename__ = "workspaces"
    active_profile_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class AgentProfile(Base, IdMixin, CreatedMixin):
    __tablename__ = "agent_profiles"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)


class AgentProfileVersion(Base, IdMixin, CreatedMixin):
    __tablename__ = "agent_profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version"),)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_profiles.id"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    source_description: Mapped[str] = mapped_column(Text, default="")
    structured_fields: Mapped[dict[str, Any]] = mapped_column(JsonType)
    context_prompt: Mapped[str] = mapped_column(Text)
    placeholders: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    generator_model: Mapped[str] = mapped_column(String(100), default="")


class Call(Base, IdMixin, CreatedMixin):
    __tablename__ = "calls"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    direction: Mapped[str] = mapped_column(String(10), default="WEB")  # WEB | OUTBOUND
    state: Mapped[str] = mapped_column(String(30), default="CREATED")
    room_name: Mapped[str] = mapped_column(String(100), unique=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    profile_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_profile_versions.id"))
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary_status: Mapped[str] = mapped_column(String(10), default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)


class CallTurn(Base, IdMixin, CreatedMixin):
    __tablename__ = "call_turns"
    __table_args__ = (UniqueConstraint("call_id", "seq"),)
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(10))  # user | agent
    text: Mapped[str] = mapped_column(Text)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class CallSummary(Base, IdMixin, CreatedMixin):
    __tablename__ = "call_summaries"
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id"), unique=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JsonType)
    model_version: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(10), default="READY")


class AuditEvent(Base, IdMixin, CreatedMixin):
    """Append-only: the service layer exposes insert only; no update/delete paths."""

    __tablename__ = "audit_events"
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    call_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor: Mapped[str] = mapped_column(String(60))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    model_versions: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
