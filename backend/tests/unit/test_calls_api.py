import json
import uuid

import jwt

from tests.conftest import INTERNAL

SECRET = "test-livekit-secret-0123456789abcdef0123"
DESC = "An appointment reminder agent for Dr. Smith's clinic."
GOOD_SUMMARY = {
    "title": "Appointment confirmed",
    "summary": "Caller confirmed.",
    "call_outcome": "completed",
    "key_points": ["confirmed"],
    "user_requests": [],
    "agent_commitments_and_next_actions": [],
    "unresolved_items": [],
    "information_collected": {"name": "Sam"},
    "sentiment": "positive",
    "escalation_needed": False,
    "escalation_reason": None,
    "topics_outside_scope_raised": [],
    "confidence_notes": "",
}


async def _setup(client):
    await client.post("/api/v1/agent-profiles/generate", json={"description": DESC})
    r = await client.post("/api/v1/calls", json={})
    assert r.status_code == 200, r.text
    return r.json()


async def test_call_requires_profile(client):
    assert (await client.post("/api/v1/calls", json={})).status_code == 404


async def test_token_has_minimal_grants_and_agent_dispatch(client):
    c = await _setup(client)
    claims = jwt.decode(c["token"], SECRET, algorithms=["HS256"], options={"verify_aud": False})
    assert claims["video"]["roomJoin"] is True and "roomAdmin" not in claims["video"]
    assert claims["exp"] - claims["nbf"] <= 600
    disp = claims["roomConfig"]["agents"][0]
    assert disp["agentName"] == "voice-agent"
    assert json.loads(disp["metadata"])["call_id"] == c["call_id"]


async def test_snapshot_version_survives_later_edits(client):
    p = (await client.post("/api/v1/agent-profiles/generate", json={"description": DESC})).json()
    c = (await client.post("/api/v1/calls", json={})).json()
    await client.put(f"/api/v1/agent-profiles/{p['profile_id']}", json={"context_prompt": "Z" * 40})
    ctx = (await client.get(f"/internal/calls/{c['call_id']}/context", headers=INTERNAL)).json()
    assert ctx["profile_version"] == 1 and "# Agent: Ava" in ctx["profile"]["context_prompt"]


async def test_internal_api_requires_token(client):
    c = await _setup(client)
    assert (await client.get(f"/internal/calls/{c['call_id']}/context")).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.get(f"/internal/calls/{c['call_id']}/context", headers=bad)).status_code == 401


async def test_workspace_isolation(client, other_client):
    c = await _setup(client)
    other_client.cookies.clear()
    assert (await other_client.get(f"/api/v1/calls/{c['call_id']}")).status_code == 404
    assert (await other_client.get("/api/v1/calls")).json() == []


async def test_turn_upsert_is_idempotent_and_ordered(client):
    c = await _setup(client)
    cid = c["call_id"]
    t = lambda seq, sp, text: {"seq": seq, "speaker": sp, "text": text}  # noqa: E731
    body = {"turns": [t(1, "agent", "Hi"), t(0, "user", "hello")]}
    for _ in range(2):  # duplicate delivery
        assert (await client.post(f"/internal/calls/{cid}/turns", json=body, headers=INTERNAL)).status_code == 200
    await client.post(f"/internal/calls/{cid}/turns", json={"turns": [t(0, "user", "hello there")]}, headers=INTERNAL)
    turns = (await client.get(f"/api/v1/calls/{cid}")).json()["turns"]
    assert [x["seq"] for x in turns] == [0, 1] and turns[0]["text"] == "hello there"


async def test_summary_flow_sets_title_and_completes(client):
    c = await _setup(client)
    cid = c["call_id"]
    await client.post(f"/internal/calls/{cid}/events", json={"type": "agent_joined"}, headers=INTERNAL)
    assert (await client.get(f"/api/v1/calls/{cid}")).json()["status"] == "ACTIVE"
    assert (await client.get(f"/api/v1/calls/{cid}")).json()["summary_status"] == "PENDING"
    r = await client.post(
        f"/internal/calls/{cid}/summary", json={"summary": GOOD_SUMMARY, "model_version": "m"}, headers=INTERNAL
    )
    assert r.json() == {"status": "READY"}
    d = (await client.get(f"/api/v1/calls/{cid}")).json()
    assert (
        d["title"] == "Appointment confirmed" and d["status"] == "COMPLETED" and d["summary"]["sentiment"] == "positive"
    )
    listing = (await client.get("/api/v1/calls")).json()
    assert listing[0]["title"] == "Appointment confirmed"


async def test_invalid_summary_rejected(client):
    c = await _setup(client)
    bad = {**GOOD_SUMMARY, "title": "x" * 80}
    r = await client.post(f"/internal/calls/{c['call_id']}/summary", json={"summary": bad}, headers=INTERNAL)
    assert r.status_code == 422
    assert (await client.get(f"/api/v1/calls/{c['call_id']}")).json()["summary_status"] == "PENDING"


async def test_failed_summary_reported(client):
    c = await _setup(client)
    await client.post(
        f"/internal/calls/{c['call_id']}/summary", json={"status": "FAILED", "error": "boom"}, headers=INTERNAL
    )
    assert (await client.get(f"/api/v1/calls/{c['call_id']}")).json()["summary_status"] == "FAILED"


async def test_fallback_summarizer_uses_persisted_turns(client, fake_gen):
    c = await _setup(client)
    cid = c["call_id"]
    turns = {"turns": [{"seq": 0, "speaker": "user", "text": "I confirm Tuesday"}]}
    await client.post(f"/internal/calls/{cid}/turns", json=turns, headers=INTERNAL)
    fake_gen.responses = [GOOD_SUMMARY]
    r = await client.post(f"/internal/calls/{cid}/summary/fallback", headers=INTERNAL)
    assert r.json() == {"status": "READY"}
    assert "USER: I confirm Tuesday" in fake_gen.calls[-1]["user"]


async def test_fallback_with_no_turns_needs_no_llm(client, fake_gen):
    c = await _setup(client)
    fake_gen.calls.clear()
    r = await client.post(f"/internal/calls/{c['call_id']}/summary/fallback", headers=INTERNAL)
    assert r.json() == {"status": "READY"} and fake_gen.calls == []
    assert (await client.get(f"/api/v1/calls/{c['call_id']}")).json()["summary"]["call_outcome"] == "abandoned"


async def test_unknown_call_404(client):
    assert (await client.get(f"/internal/calls/{uuid.uuid4()}/context", headers=INTERNAL)).status_code == 404
