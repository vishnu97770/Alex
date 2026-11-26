from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from app.core.config import get_settings
from app.services import bulk_jobs_service
from tests.conftest import INTERNAL
from tests.unit.test_accounts_api import make_agent, register
from tests.unit.test_phone_calls_api import dispatched, phone_on  # noqa: F401  (pytest fixtures)

CSV = (
    "name,phone,amount,deadline,lender,loan reference,notes\n"
    "Asha Rao,+91 98123 45678,12000,30/11/2026,Sunrise Bank,LN-1,Prefers evenings\n"
    "Ravi Kumar,+91 98765 43210,5200.50,2026-12-05,,,\n"
    "Bad Row,12345,0,,,,\n"
)
HEADERS = {"Content-Type": "text/csv"}


async def _start(client: AsyncClient) -> tuple[str, dict[str, Any]]:
    u = await register(client)
    await make_agent(client, u["uid"], "Maya")
    r = await client.post(
        f"/api/v1/users/{u['uid']}/bulk-calls", params={"file_name": "october.csv"}, content=CSV, headers=HEADERS
    )
    assert r.status_code == 201, r.text
    return str(u["uid"]), r.json()


async def _tick(sm: Any, now: datetime | None = None) -> None:
    async with sm() as s:
        await bulk_jobs_service.tick(s, get_settings(), now)


async def _event(client: AsyncClient, call_id: str, kind: str, **payload: Any) -> None:
    body = {"type": kind, "payload": payload}
    assert (await client.post(f"/internal/calls/{call_id}/events", json=body, headers=INTERNAL)).status_code == 200


async def _current(client: AsyncClient, uid: str) -> dict[str, Any]:
    r = await client.get(f"/api/v1/users/{uid}/bulk-calls/current")
    assert r.status_code == 200
    return r.json()  # type: ignore[no-any-return]


async def test_bulk_calls_need_phone_calls_set_up(client: AsyncClient) -> None:
    u = await register(client)
    await make_agent(client, u["uid"])
    r = await client.post(f"/api/v1/users/{u['uid']}/bulk-calls", content=CSV, headers=HEADERS)
    assert r.status_code == 409 and "not set up" in r.text
    assert (await client.get(f"/api/v1/users/{u['uid']}/bulk-calls/current")).json() is None


async def test_valid_rows_are_called_one_at_a_time_and_results_recorded(
    phone_on: None,  # noqa: F811
    client: AsyncClient,
    dispatched: list[dict[str, Any]],  # noqa: F811
    app_and_sm: Any,
) -> None:
    _, sm = app_and_sm
    uid, job = await _start(client)
    assert job["status"] == "running" and job["file_name"] == "october.csv" and job["total"] == 2  # bad row dropped
    assert [i["phone_last4"] for i in job["items"]] == ["5678", "3210"]
    assert "98123" not in str(job) and "98765" not in str(job)  # only the last 4 digits are ever returned
    again = await client.post(f"/api/v1/users/{uid}/bulk-calls", content=CSV, headers=HEADERS)
    assert again.status_code == 409  # one run at a time

    await _tick(sm)  # first borrower is called
    await _tick(sm)  # ...and nobody else while that call is on
    cur = await _current(client, uid)
    assert [i["status"] for i in cur["items"]] == ["calling", "pending"] and len(dispatched) == 1
    first = cur["items"][0]["call_id"]
    ctx = (await client.get(f"/internal/calls/{first}/context", headers=INTERNAL)).json()
    assert ctx["dial"]["to"] == "+919812345678"
    prompt = ctx["profile"]["context_prompt"]
    assert "Asha Rao" in prompt and "Sunrise Bank" in prompt and "30 November 2026" in prompt and "LN-1" in prompt

    await _event(client, first, "answered")
    await _event(client, first, "session_closed", reason="participant_disconnected")
    await _tick(sm)  # first is done; second is called
    cur = await _current(client, uid)
    assert [(i["status"], i["result"]) for i in cur["items"]] == [("done", "answered"), ("calling", None)]
    second = cur["items"][1]["call_id"]

    await _event(client, second, "dial_failed", reason="busy", sip_status_code=486)
    await _tick(sm)
    cur = await _current(client, uid)
    assert cur["status"] == "done" and cur["answered"] == 1
    assert [(i["status"], i["result"]) for i in cur["items"]] == [("done", "answered"), ("done", "busy")]
    assert len(dispatched) == 2


async def test_pause_resume_cancel(
    phone_on: None,  # noqa: F811
    client: AsyncClient,
    other_client: AsyncClient,
    dispatched: list[Any],  # noqa: F811
    app_and_sm: Any,
) -> None:
    _, sm = app_and_sm
    uid, job = await _start(client)
    url = f"/api/v1/users/{uid}/bulk-calls/{job['job_id']}"
    assert (await client.post(f"{url}/pause")).json()["status"] == "paused"
    await _tick(sm)
    assert dispatched == []  # nothing is called while paused
    assert (await client.post(f"{url}/pause")).status_code == 409
    assert (await client.post(f"{url}/resume")).json()["status"] == "running"
    await _tick(sm)
    assert len(dispatched) == 1
    await register(other_client, "bob@example.com", "Bob")
    assert (await other_client.post(f"{url}/cancel")).status_code == 403  # not their run
    cancelled = (await client.post(f"{url}/cancel")).json()
    assert cancelled["status"] == "cancelled"
    assert [(i["status"], i["result"]) for i in cancelled["items"]] == [("calling", None), ("skipped", "cancelled")]
    first = cancelled["items"][0]["call_id"]
    await _event(client, first, "session_closed", reason="hangup")  # the call in progress finishes normally
    await _tick(sm)
    cur = await _current(client, uid)
    assert cur["items"][0] == {**cur["items"][0], "status": "done", "result": "answered"} and len(dispatched) == 1
    assert (await client.post(f"{url}/cancel")).status_code == 409
    assert (await client.post(f"/api/v1/users/{uid}/bulk-calls/{job['job_id']}/explode")).status_code == 422


async def test_a_lost_call_does_not_block_the_queue(
    phone_on: None,  # noqa: F811
    client: AsyncClient,
    dispatched: list[Any],  # noqa: F811
    app_and_sm: Any,
) -> None:
    _, sm = app_and_sm
    uid, _ = await _start(client)
    await _tick(sm)
    await _tick(sm, datetime.now(UTC) + timedelta(minutes=31))  # the worker never reported the end
    cur = await _current(client, uid)
    assert [(i["status"], i["result"]) for i in cur["items"]][0] == ("done", "dial_failed")


async def test_deleting_the_agent_cancels_the_rest(
    phone_on: None,  # noqa: F811
    client: AsyncClient,
    dispatched: list[Any],  # noqa: F811
    app_and_sm: Any,
) -> None:
    _, sm = app_and_sm
    uid, job = await _start(client)
    await client.post(f"/api/v1/users/{uid}/bulk-calls/{job['job_id']}/pause")
    assert (await client.delete(f"/api/v1/users/{uid}/agent")).status_code == 204
    await client.post(f"/api/v1/users/{uid}/bulk-calls/{job['job_id']}/resume")
    await _tick(sm)
    cur = await _current(client, uid)
    assert cur["status"] == "cancelled" and {i["result"] for i in cur["items"]} == {"agent_gone"} and dispatched == []
