import asyncio
from types import SimpleNamespace

import pytest

from voice_agent.lifecycle.transcript_recorder import TranscriptRecorder, item_to_turn
from voice_agent.tools.base import CallState, ToolContext
from voice_agent.tools.registry import UnknownToolError, build_tools


class FakeBackend:
    def __init__(self):
        self.turns, self.events, self.summaries, self.fallbacks = [], [], [], 0
        self.fail_turns = 0

    async def post_turns(self, call_id, turns):
        if self.fail_turns:
            self.fail_turns -= 1
            raise RuntimeError("down")
        self.turns += turns

    async def post_event(self, call_id, t, payload=None):
        self.events.append((t, payload))

    async def post_summary(self, call_id, body):
        self.summaries.append(body)

    async def request_fallback_summary(self, call_id):
        self.fallbacks += 1


def msg(role, text, id_="i1", **kw):
    return SimpleNamespace(
        type="message", role=role, text_content=text, id=id_, interrupted=False, metrics=kw.get("metrics")
    )


def test_end_call_always_present_and_unknown_tool_fails_closed():
    ctx = ToolContext(state=CallState("c", "k"), backend=FakeBackend())
    assert [t.info.name for t in build_tools([], ctx)] == ["end_call"]
    with pytest.raises(UnknownToolError):
        build_tools(["get_secrets"], ctx)


def test_item_to_turn_filters_and_maps_metrics():
    assert item_to_turn(msg("system", "x"), 0) is None
    assert item_to_turn(msg("user", "   "), 0) is None
    t = item_to_turn(msg("assistant", "Hi", metrics={"e2e_latency": 0.7, "junk": 1}), 3)
    assert t["speaker"] == "agent" and t["seq"] == 3 and t["metrics_json"] == {"e2e_latency": 0.7}


async def test_recorder_dedupes_orders_and_survives_backend_errors():
    be = FakeBackend()
    be.fail_turns = 1
    rec = TranscriptRecorder(be, "c1")
    handlers = {}
    rec.attach(SimpleNamespace(on=lambda ev, fn: handlers.setdefault(ev, fn)))
    h = handlers["conversation_item_added"]
    h(SimpleNamespace(item=msg("user", "hello", "a")))
    h(SimpleNamespace(item=msg("user", "hello", "a")))  # duplicate event
    h(SimpleNamespace(item=msg("assistant", "hi there", "b")))
    await rec.flush()
    assert [t["seq"] for t in rec.turns] == [0, 1]
    assert [t["seq"] for t in be.turns] == [1]  # seq 0 failed once; local copy is kept for the summary
    await asyncio.sleep(0)
