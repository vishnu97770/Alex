"""Explicit state machines. Illegal transitions raise; callers audit each transition."""

from enum import StrEnum

from app.core.errors import IllegalTransition


class StateMachine[S: StrEnum]:
    def __init__(self, name: str, transitions: dict[S, set[S]]):
        self.name = name
        self._t = transitions

    def can(self, src: S, dst: S) -> bool:
        return dst in self._t.get(src, set())

    def check(self, src: S, dst: S) -> S:
        if not self.can(src, dst):
            raise IllegalTransition(f"{self.name}: illegal transition {src} -> {dst}")
        return dst


class ApplicationState(StrEnum):
    DRAFT = "DRAFT"
    DOCUMENTS_UPLOADED = "DOCUMENTS_UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    ANALYSIS_READY = "ANALYSIS_READY"
    UNDER_REVIEW = "UNDER_REVIEW"
    DECIDED = "DECIDED"


class VoiceSessionState(StrEnum):
    SESSION_CONNECTING = "SESSION_CONNECTING"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    SESSION_END = "SESSION_END"


class OutboundState(StrEnum):
    SCHEDULED = "SCHEDULED"
    TRIGGERED = "TRIGGERED"
    INITIATING = "INITIATING"
    RINGING = "RINGING"
    CONNECTED = "CONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    CONVERSING = "CONVERSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    AUDITED = "AUDITED"


class CallState(StrEnum):
    """Lifecycle of a browser (WEB) call record."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


A, V, OS_, C = ApplicationState, VoiceSessionState, OutboundState, CallState

APPLICATION = StateMachine[ApplicationState](
    "application",
    {
        A.DRAFT: {A.DOCUMENTS_UPLOADED},
        A.DOCUMENTS_UPLOADED: {A.PROCESSING},
        A.PROCESSING: {A.ANALYSIS_READY, A.PROCESSING_FAILED},
        A.PROCESSING_FAILED: {A.PROCESSING},
        A.ANALYSIS_READY: {A.UNDER_REVIEW},
        A.UNDER_REVIEW: {A.DECIDED},
    },
)

VOICE_SESSION = StateMachine[VoiceSessionState](
    "voice_session",
    {
        V.SESSION_CONNECTING: {V.LISTENING, V.SESSION_END},
        V.LISTENING: {V.PROCESSING, V.SPEAKING, V.SESSION_END},
        V.PROCESSING: {V.SPEAKING, V.LISTENING, V.INTERRUPTED, V.SESSION_END},
        V.SPEAKING: {V.INTERRUPTED, V.LISTENING, V.SESSION_END},
        V.INTERRUPTED: {V.LISTENING, V.PROCESSING, V.SESSION_END},
    },
)

OUTBOUND = StateMachine[OutboundState](
    "outbound_call",
    {
        OS_.SCHEDULED: {OS_.TRIGGERED, OS_.FAILED},
        OS_.TRIGGERED: {OS_.INITIATING, OS_.FAILED},
        OS_.INITIATING: {OS_.RINGING, OS_.FAILED},
        OS_.RINGING: {OS_.CONNECTED, OS_.FAILED},
        OS_.CONNECTED: {OS_.AUTHENTICATING, OS_.CONTEXT_LOADING, OS_.FAILED},
        OS_.AUTHENTICATING: {OS_.CONTEXT_LOADING, OS_.COMPLETED, OS_.FAILED},
        OS_.CONTEXT_LOADING: {OS_.CONVERSING, OS_.FAILED},
        OS_.CONVERSING: {OS_.COMPLETED, OS_.FAILED},
        OS_.COMPLETED: {OS_.AUDITED},
        OS_.FAILED: {OS_.AUDITED},
    },
)

CALL = StateMachine[CallState](
    "call",
    {
        C.CREATED: {C.ACTIVE, C.FAILED, C.COMPLETED},
        C.ACTIVE: {C.COMPLETED, C.FAILED},
    },
)
