"""Hindi and English on one call: hear both, and speak each reply in a voice that can say it."""

import asyncio
from types import SimpleNamespace

import pytest
from livekit.agents import Agent, inference

from voice_agent.bilingual import BilingualAgent, is_hindi, peek_language
from voice_agent.config import get_settings
from voice_agent.profile.prompt_composer import RuntimeContext
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.providers.stt import build_stt
from voice_agent.providers.tts import build_hindi_tts
from voice_agent.session_factory import build_agent

PROFILE = AgentProfileSpec.model_validate(
    {"identity": {"agent_name": "Maya"}, "context_prompt": "p", "voice_behavior": {"hindi_voice_id": "voice-hi"}}
)


async def chunks(*parts):
    for p in parts:
        yield p


async def collect(it):
    return [x async for x in it]


def test_speech_recognition_detects_the_language_by_itself():
    opts = build_stt(get_settings())._opts
    assert opts.language == "multi"
    assert opts.endpointing_ms == 100  # what Deepgram recommends for speech that mixes languages


async def test_speech_recognition_expects_only_english_and_hindi(monkeypatch):
    """Without the hints, short answers drifted to other languages: "ठीक है" (okay) was heard as Indonesian "Tidak" (no).
    Reads the address the plugin really connects to, so a plugin upgrade that drops the hints fails here."""
    urls = []

    class Session:
        async def ws_connect(self, url, **_):
            urls.append(url)
            raise RuntimeError("no network in tests")

    monkeypatch.setattr("livekit.agents.utils.http_context.http_session", Session)
    stream = build_stt(get_settings()).stream()
    with pytest.raises(Exception):  # noqa: B017  (however the plugin reports the refused connection)
        await stream._connect_ws()
    await stream.aclose()
    assert "language=multi" in urls[0] and "language_hint=en&language_hint=hi" in urls[0]


def test_hints_are_left_out_when_one_language_is_fixed():
    s = get_settings().model_copy(update={"stt_language": "en-US"})
    assert build_stt(s)._session is None


@pytest.mark.parametrize(
    ("text", "hindi"),
    [
        ("Hello, am I speaking with Vishnu?", False),
        ("जी, मैं समझता हूँ।", True),
        ("Vishnu जी, नमस्ते", True),
        ("", False),
        ("12,345", False),
    ],
)
def test_is_hindi(text, hindi):
    assert is_hindi(text) is hindi


async def test_peek_keeps_every_chunk_and_reads_past_a_leading_english_name():
    hindi, text = await peek_language(chunks("Vish", "nu ", "जी, ", "नमस्ते", "।"))
    assert hindi and await collect(text) == ["Vish", "nu ", "जी, ", "नमस्ते", "।"]


async def test_peek_decides_english_without_waiting_for_the_whole_reply():
    released = asyncio.Event()

    async def slow():
        yield "I understand, that sounds hard. "
        await released.wait()
        yield "When can you pay?"

    hindi, text = await asyncio.wait_for(peek_language(slow()), 1)
    released.set()
    assert not hindi and await collect(text) == ["I understand, that sounds hard. ", "When can you pay?"]


async def test_peek_handles_a_reply_shorter_than_the_window():
    hindi, text = await peek_language(chunks("जी"))
    assert hindi and await collect(text) == ["जी"]


class FakeHindiTTS:
    """Stands in for the Cartesia voice: records what it was asked to say."""

    def __init__(self):
        self.said, self.prewarmed, self.closed = [], 0, False

    def prewarm(self):
        self.prewarmed += 1

    def stream(self, **_):
        outer = self

        class Stream:
            def __init__(self):
                self.done = asyncio.Event()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return None

            def push_text(self, t):
                outer.said.append(t)

            def end_input(self):
                self.done.set()

            async def __aiter__(self):
                await self.done.wait()
                yield SimpleNamespace(frame="hindi-audio")

        return Stream()


@pytest.fixture
def english_voice(monkeypatch):
    said = []

    async def node(agent, text, model_settings):
        said.extend([c async for c in text])
        yield "english-audio"

    monkeypatch.setattr(Agent.default, "tts_node", staticmethod(node))
    return said


async def test_hindi_reply_is_spoken_by_the_hindi_voice(english_voice):
    hi = FakeHindiTTS()
    agent = BilingualAgent(instructions="x", hindi_tts=hi)
    assert await collect(agent.tts_node(chunks("जी, ", "बताइए"), None)) == ["hindi-audio"]
    assert hi.said == ["जी, ", "बताइए"] and english_voice == []


async def test_english_reply_keeps_the_agents_own_voice(english_voice):
    hi = FakeHindiTTS()
    agent = BilingualAgent(instructions="x", hindi_tts=hi)
    assert await collect(agent.tts_node(chunks("Sure, ", "tell me more please"), None)) == ["english-audio"]
    assert english_voice == ["Sure, ", "tell me more please"] and hi.said == []


async def test_without_a_hindi_voice_everything_uses_the_agents_own_voice(english_voice):
    agent = BilingualAgent(instructions="x", hindi_tts=None)
    assert await collect(agent.tts_node(chunks("जी"), None)) == ["english-audio"]


def test_hindi_voice_is_a_hindi_cartesia_voice_on_livekit_inference():
    tts = build_hindi_tts(get_settings(), "voice-hi")
    assert isinstance(tts, inference.TTS)
    assert (tts._opts.model, tts._opts.voice, tts._opts.language) == ("cartesia/sonic-3", "voice-hi", "hi")
    assert build_hindi_tts(get_settings(), " ") is None


def test_calls_are_run_by_the_bilingual_agent():
    hi = FakeHindiTTS()
    agent = build_agent(PROFILE, RuntimeContext("WEB", "now"), [], hindi_tts=hi)
    assert isinstance(agent, BilingualAgent) and agent.hindi_tts is hi
