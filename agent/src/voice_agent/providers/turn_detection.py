import logging
from typing import Any

from voice_agent.config import AgentSettings

log = logging.getLogger("turn_detection")


def build_turn_detection(s: AgentSettings) -> Any:
    """'semantic' = LiveKit inference TurnDetector (local fallback built in); else a framework literal."""
    if s.turn_detection == "semantic":
        try:
            from livekit.agents import inference

            return inference.TurnDetector()
        except Exception:
            log.exception("semantic turn detector unavailable, falling back to VAD")
            return "vad"
    return s.turn_detection
