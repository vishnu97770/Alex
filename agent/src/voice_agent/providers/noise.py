from collections.abc import Callable
from typing import Any

from livekit import rtc
from livekit.plugins import noise_cancellation

from voice_agent.config import AgentSettings


def noise_selector(s: AgentSettings) -> Callable[[Any], Any] | None:
    """BVCTelephony for SIP participants, BVC for web. LiveKit Cloud only; disabled via config."""
    if not s.enable_noise_cancellation:
        return None

    def select(params: Any) -> Any:
        if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return noise_cancellation.BVCTelephony()
        return noise_cancellation.BVC()

    return select
