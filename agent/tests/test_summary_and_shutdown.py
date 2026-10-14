import asyncio

import pytest

from tests.test_tools_and_recorder import FakeBackend
from voice_agent.lifecycle.shutdown import finalize_call
from voice_agent.lifecycle.summarizer import summarize
from voice_agent.lifecycle.transcript_recorder import TranscriptRecorder
from voice_agent.tools.base import CallState

GOOD = {
    "title": "Booked a demo",
    "summary": "s",
    "call_outcome": "completed",
    "key_points": [],
    "user_requests": [],
    "agent_commitments_and_next_actions": [],
    "unresolved_items": [],
    "information_collected": {},
    "sentiment": "neutral",
    "escalation_needed": False,
    "escalation_reason": None,
    "topics_outside_scope_raised": [],
    "confidence_notes": "",
}
TURNS = [{"speaker": "user", "text": "hi", "is_final": True}]


class Gen:
    def __init__(self, outs):
        self.outs, self.users = list(outs), []

    async def generate(self, system, user, schema):
        self.users.append(user)
        o = self.outs.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


async def test_summary_repair_retry_then_success():
    g = Gen([{"title": "x"}, GOOD])
    assert (await summarize(TURNS, g))["title"] == "Booked a demo"
    assert "previous output was invalid" in g.users[1]


async def test_summary_fails_after_one_repair():
    with pytest.raises(ValueError):
        await summarize(TURNS, Gen([{}, {}]))


def _setup(turns):
    be = FakeBackend()
    rec = TranscriptRecorder(be, "c")
    rec.turns = turns
    closed = asyncio.Event()
    closed.set()
    return be, rec, closed


async def _run(be, rec, closed, gen):
    await finalize_call(
        state=CallState("c", "k"),
        recorder=rec,
        backend=be,
        generator=gen,
        model_version="m",
        closed=closed,
        reason="closed",
        timeout=2,
        extensions=None,
    )


async def test_shutdown_posts_summary():
    be, rec, closed = _setup(TURNS)
    await _run(be, rec, closed, Gen([GOOD]))
    assert be.summaries[0]["summary"]["title"] == "Booked a demo" and be.fallbacks == 0
    assert be.events[0][0] == "session_closed"


async def test_shutdown_falls_back_to_backend_when_llm_fails():
    be, rec, closed = _setup(TURNS)
    await _run(be, rec, closed, Gen([RuntimeError("llm down")]))
    assert be.summaries == [] and be.fallbacks == 1


async def test_shutdown_with_no_turns_uses_backend_fallback_without_llm():
    be, rec, closed = _setup([])
    gen = Gen([])
    await _run(be, rec, closed, gen)
    assert be.fallbacks == 1 and gen.users == []
