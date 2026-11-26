"""How fast a call starts and how soon the agent answers: no waiting on things that could already be done."""

import asyncio
import subprocess
import sys
from types import SimpleNamespace

import pytest

from voice_agent import worker
from voice_agent.config import get_settings
from voice_agent.profile.schema import AgentProfileSpec
from voice_agent.session_factory import build_turn_handling

PROFILE = {
    "identity": {"agent_name": "Maya"},
    "context_prompt": "p",
    "voice_behavior": {"latency_profile": "aggressive", "greeting": "Hello"},
}
CONTEXT = {
    "profile": PROFILE,
    "correlation_id": "k",
    "direction": "WEB",
    "runtime": {"now_utc": "n", "timezone": "UTC"},
}


def test_the_wait_after_the_caller_stops_never_grows_during_a_call():
    """With "dynamic" endpointing, one long pause raised the wait to 1.6s for the whole of the rest of the call."""
    ep = build_turn_handling(AgentProfileSpec.model_validate(PROFILE), get_settings(), "vad")["endpointing"]
    assert ep["mode"] == "fixed"


def test_the_longest_wait_for_an_unfinished_sounding_answer_is_short():
    ep = build_turn_handling(AgentProfileSpec.model_validate(PROFILE), get_settings(), "vad")["endpointing"]
    assert ep["min_delay"] <= 0.2 and ep["max_delay"] <= 1.2


def test_network_libraries_are_loaded_before_a_call_arrives():
    """Importing them on the first call blocked the agent's event loop for about 0.7s."""
    code = (
        "import sys, voice_agent.worker as w; w.preload_network();"
        "print(all(m in sys.modules for m in"
        " ('httpcore._sync.connection', 'anyio._backends._asyncio', 'anyio._core._sockets')))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.stdout.strip().endswith("True"), out.stderr[-500:]


def test_prewarm_loads_the_voice_detector_and_the_network_libraries(monkeypatch):
    done = []
    monkeypatch.setattr(worker, "load_vad", lambda: "vad")
    monkeypatch.setattr(worker, "preload_network", lambda: done.append("network"))
    proc = SimpleNamespace(userdata={})
    worker.prewarm(proc)
    assert proc.userdata["vad"] == "vad" and done == ["network"]


class FakeBackend:
    def __init__(self, fail=False):
        self.asked, self.fail = asyncio.Event(), fail

    async def get_context(self, call_id):
        self.asked.set()
        if self.fail:
            raise RuntimeError("backend down")
        return CONTEXT


@pytest.fixture
def session(monkeypatch):
    s = SimpleNamespace(tts=SimpleNamespace(prewarmed=asyncio.Event()))
    s.tts.prewarm = s.tts.prewarmed.set
    monkeypatch.setattr(worker, "build_session", lambda *a, **k: s)
    return s


async def test_call_details_load_and_the_voice_connects_while_the_room_is_joined(session):
    backend = FakeBackend()

    async def connect():  # joining finishes only after the details were asked for and the voice started connecting
        await asyncio.wait_for(backend.asked.wait(), 1)
        await asyncio.wait_for(session.tts.prewarmed.wait(), 1)

    call = await asyncio.wait_for(
        worker.open_call(SimpleNamespace(connect=connect), backend, "c1", get_settings(), vad=None), 2
    )
    assert call.session is session and call.state.call_id == "c1" and call.profile.identity.agent_name == "Maya"


async def test_a_failure_loading_the_call_is_not_swallowed(session):
    async def connect():
        return None

    with pytest.raises(RuntimeError, match="backend down"):
        await worker.open_call(SimpleNamespace(connect=connect), FakeBackend(fail=True), "c1", get_settings(), vad=None)


def test_agent_keeps_reconnecting_through_an_internet_outage():
    """The framework gives up after 16 tries (about 2.5 minutes): a Wi-Fi drop on 26 Nov left the agent shut down, and
    calls unanswered, until someone restarted it by hand."""
    opts = worker.worker_options()
    assert opts.max_retry * 10 >= 12 * 3600  # retries are 10s apart once backed off: keeps trying for 12h or more
    assert opts.entrypoint_fnc is worker.entrypoint and opts.prewarm_fnc is worker.prewarm
