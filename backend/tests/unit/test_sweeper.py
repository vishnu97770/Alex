from datetime import UTC, datetime, timedelta

from app.workers.sweeper import sweep_once
from tests.conftest import INTERNAL
from tests.unit.test_calls_api import GOOD_SUMMARY, _setup


async def test_sweeper_summarizes_ended_call_after_grace(client, app_and_sm, fake_gen):
    _, sm = app_and_sm
    c = await _setup(client)
    await client.post(
        f"/internal/calls/{c['call_id']}/turns",
        json={"turns": [{"seq": 0, "speaker": "user", "text": "hi"}]},
        headers=INTERNAL,
    )
    await client.post(f"/internal/calls/{c['call_id']}/events", json={"type": "session_closed"}, headers=INTERNAL)
    fake_gen.responses = [GOOD_SUMMARY]
    async with sm() as s:
        assert await sweep_once(s, fake_gen, "m") == 0  # inside grace window
        later = datetime.now(UTC) + timedelta(minutes=5)
        assert await sweep_once(s, fake_gen, "m", now=later) == 1
    assert (await client.get(f"/api/v1/calls/{c['call_id']}")).json()["summary_status"] == "READY"


async def test_sweeper_recovers_silent_live_call_as_worker_lost(client, app_and_sm, fake_gen):
    _, sm = app_and_sm
    c = await _setup(client)
    async with sm() as s:
        later = datetime.now(UTC) + timedelta(hours=2)
        assert await sweep_once(s, fake_gen, "m", now=later) == 1
    d = (await client.get(f"/api/v1/calls/{c['call_id']}")).json()
    assert d["summary_status"] == "READY" and d["end_reason"] == "worker_lost"
