from typing import Any
from urllib.parse import urlencode

from livekit.agents import stt, utils
from livekit.plugins import deepgram

from voice_agent.config import AgentSettings

# Silence that ends a piece of speech, in ms. Deepgram recommends 100 when the speaker may switch language.
MULTI_ENDPOINTING_MS = 100


class _HintedSession:
    """The job's HTTP session, adding Deepgram's `language_hint` to streaming connections. The hints are what keep short
    answers in the languages we speak: without them "ठीक है" (okay) was heard as Indonesian "Tidak" (no). The plugin has
    no option for them with nova-3."""

    def __init__(self, hints: list[str]) -> None:
        self._query = urlencode({"language_hint": hints}, doseq=True)

    def ws_connect(self, url: str, **kwargs: Any) -> Any:
        return utils.http_context.http_session().ws_connect(f"{url}&{self._query}", **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(utils.http_context.http_session(), name)


def build_stt(s: AgentSettings) -> stt.STT:
    if s.stt_provider == "deepgram":
        kw: dict[str, Any] = {}
        hints = [h.strip() for h in s.stt_language_hints.split(",") if h.strip()]
        if s.stt_language == "multi":
            kw["endpointing_ms"] = MULTI_ENDPOINTING_MS
            if hints:
                kw["http_session"] = _HintedSession(hints)
        return deepgram.STT(
            model=s.stt_model, language=s.stt_language, interim_results=True, api_key=s.deepgram_api_key, **kw
        )
    raise ValueError(f"unsupported STT provider {s.stt_provider}")
