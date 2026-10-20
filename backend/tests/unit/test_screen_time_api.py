from datetime import date, timedelta

from httpx import AsyncClient

from tests.unit.test_accounts_api import register


async def test_heartbeat_accumulates_and_caps(client: AsyncClient) -> None:
    u = await register(client)
    url = f"/api/v1/users/{u['uid']}/screen-time"
    assert (await client.post(f"{url}/heartbeat", json={"seconds": 30})).status_code == 204
    # an immediate second beat cannot claim 60 more seconds of real time
    assert (await client.post(f"{url}/heartbeat", json={"seconds": 60})).status_code == 204
    week = (await client.get(url)).json()
    today = next(d for d in week["days"] if d["date"] == week["today"])
    assert 30 <= today["hours"] * 3600 <= 35
    assert len(week["days"]) == 7 and week["days"][0]["weekday"] == "Mon"
    for bad in (0, 61, -5):
        assert (await client.post(f"{url}/heartbeat", json={"seconds": bad})).status_code == 422
    assert (await client.post(f"{url}/heartbeat", json={"seconds": 5, "tz": "Nope/Zone"})).status_code == 422


async def test_week_param_and_empty_weeks_are_zero(client: AsyncClient) -> None:
    u = await register(client)
    url = f"/api/v1/users/{u['uid']}/screen-time"
    last = (date.today() - timedelta(days=14)).isoformat()
    w = (await client.get(url, params={"week_start": last})).json()
    assert all(d["hours"] == 0 for d in w["days"])
    assert (await client.get(url, params={"week_start": "nope"})).status_code == 422


async def test_screen_time_requires_csrf_and_own_uid(client: AsyncClient, other_client: AsyncClient) -> None:
    a = await register(client)
    await register(other_client, "bob@example.com", "Bob")
    assert (
        await other_client.post(f"/api/v1/users/{a['uid']}/screen-time/heartbeat", json={"seconds": 5})
    ).status_code == 403
    del client.headers["X-CSRF-Token"]
    assert (
        await client.post(f"/api/v1/users/{a['uid']}/screen-time/heartbeat", json={"seconds": 5})
    ).status_code == 403
