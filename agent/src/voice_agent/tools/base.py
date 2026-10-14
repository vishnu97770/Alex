from dataclasses import dataclass, field
from typing import Any

from voice_agent.backend_client import BackendClient


@dataclass
class CallState:
    call_id: str
    correlation_id: str
    direction: str = "WEB"
    end_reason: str | None = None
    user_turns: int = 0  # finalized caller utterances so far
    end_proposed_at: int | None = None  # user_turns value when the agent announced it would end the call
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    state: CallState
    backend: BackendClient
    session: Any = None  # AgentSession, set after construction
