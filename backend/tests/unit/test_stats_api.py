import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from app.db.models import Call, CallLink
from tests.unit.test_accounts_api import _make_agent, register


async def _active_agent(c: AsyncClient, uid: str, name: str = "Ava") -> str:
    aid = await _make_agent(c, uid, name)
    await c.post(f"/api/v1/users/{uid}/agents/{aid}/payment", json={"amount": 100})
    return aid


async def _add_call(
    sm: Any, uid: str, *, agent: str | None, mid: uuid.UUID | None = None, start: datetime, minutes: float | None
) -> None:
    from app.db.models import AgentProfile, AgentProfileVersion, User

    async with sm() as s:
        user = await s.get(User, uuid.UUID(uid))
        assert user is not None
        pv = (await s.scalars(__import__("sqlalchemy").select(AgentProfileVersion).limit(1))).first()
        if pv is None:
            ap = AgentProfile(workspace_id=user.workspace_id, source="t")
            s.add(ap)
            await s.flush()
            pv = AgentProfileVersion(
                profile_id=ap.id, version=1, source="t", fields_json={}, context_prompt="p", model="m"
            )
            s.add(pv)
            await s.flush()
        cid = uuid.uuid4()
        call = Call(
            id=cid,
            workspace_id=user.workspace_id,
            room_name=f"r-{cid}",
            correlation_id="c",
            profile_version_id=pv.id,
            started_at=start,
            created_at=start,
            ended_at=None if minutes is None else start + timedelta(minutes=minutes),
        )
        s.add(call)
        await s.flush()
        s.add(CallLink(call_id=cid, uid=user.uid, agent_aid=uuid.UUID(agent) if agent else None, manager_mid=mid))
        await s.commit()


async def test_usage_zero_series_and_validation(client: AsyncClient) -> None:
    u = await register(client)
    aid = await _active_agent(client, u["uid"])
    base = f"/api/v1/users/{u['uid']}/stats/usage"
    r = await client.get(base, params={"metric": "calls", "range": "28d"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["buckets"]) == 28 and body["tz"] == "UTC"
    assert [s["name"] for s in body["series"]] == ["Ava", "Manager"]
    assert all(sum(s["points"]) == 0 and len(s["points"]) == 28 for s in body["series"])
    assert len((await client.get(base, params={"metric": "minutes", "range": "today"})).json()["buckets"]) == 24
    assert (await client.get(base, params={"metric": "bogus", "range": "7d"})).status_code == 422
    assert (await client.get(base, params={"metric": "calls", "range": "1y"})).status_code == 422
    assert (await client.get(base, params={"metric": "calls", "range": "7d", "tz": "Nope/Zone"})).status_code == 422
    assert (await client.get(base, params={"metric": "calls", "range": "7d", "agent_id": aid})).status_code == 200


async def test_usage_counts_minutes_rule_and_agent_filter(client: AsyncClient, app_and_sm: Any) -> None:
    _, sm = app_and_sm
    u = await register(client)
    aid = await _active_agent(client, u["uid"])
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    await _add_call(sm, u["uid"], agent=aid, start=now, minutes=10)
    await _add_call(sm, u["uid"], agent=aid, start=now, minutes=None)  # never ended: no minutes
    await _add_call(sm, u["uid"], agent=aid, start=now, minutes=5000)  # capped at 120
    base = f"/api/v1/users/{u['uid']}/stats/usage"
    calls = (await client.get(base, params={"metric": "calls", "range": "7d", "agent_id": aid})).json()
    assert sum(calls["series"][0]["points"]) == 3 and calls["series"][0]["points"][-1] == 3
    mins = (await client.get(base, params={"metric": "minutes", "range": "7d", "agent_id": aid})).json()
    assert sum(mins["series"][0]["points"]) == 130.0
    assert len(mins["series"]) == 1


async def test_usage_agent_filter_ownership(client: AsyncClient, other_client: AsyncClient) -> None:
    a = await register(client)
    b = await register(other_client, "bob@example.com", "Bob")
    aid = await _active_agent(client, a["uid"])
    q = {"metric": "calls", "range": "7d"}
    mine = await other_client.get(f"/api/v1/users/{b['uid']}/stats/usage", params={**q, "agent_id": aid})
    missing = await other_client.get(
        f"/api/v1/users/{b['uid']}/stats/usage", params={**q, "agent_id": str(uuid.uuid4())}
    )
    assert mine.status_code == missing.status_code == 404
    assert mine.json()["error"]["message"] == missing.json()["error"]["message"]
    assert (await other_client.get(f"/api/v1/users/{a['uid']}/stats/usage", params=q)).status_code == 403
