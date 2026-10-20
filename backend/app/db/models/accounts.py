import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedMixin, IdMixin, utcnow


class User(Base, CreatedMixin):
    """A signed-in person. `workspace_id` ties them to the pre-existing call/profile data (1:1)."""

    __tablename__ = "users"
    uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # None for Google-only users
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), unique=True)


class Agent(Base, CreatedMixin):
    """A user-defined voice agent. PENDING until the payment step succeeds, then ACTIVE."""

    __tablename__ = "agents"
    aid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.uid"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    role_behavior: Mapped[str] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(String(10), default="PENDING")  # PENDING | ACTIVE
    profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_profiles.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Manager(Base, CreatedMixin):
    """One per user: the voice agent that knows about all of the user's agents."""

    __tablename__ = "managers"
    mid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.uid"), unique=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_profiles.id"), nullable=True)


class AgentPayment(Base, IdMixin, CreatedMixin):
    """Simulated payment attempts (no real gateway)."""

    __tablename__ = "agent_payments"
    aid: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.aid"), index=True)
    uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.uid"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10))  # SUCCEEDED | REJECTED


class CallLink(Base, CreatedMixin):
    """Says whose call this is (a manager call or an agent call) without touching the `calls` table."""

    __tablename__ = "call_links"
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id"), primary_key=True)
    uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.uid"), index=True)
    manager_mid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("managers.mid"), nullable=True, index=True)
    agent_aid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.aid"), nullable=True, index=True)
