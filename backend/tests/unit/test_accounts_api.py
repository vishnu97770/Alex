import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import get_settings

PW = "correct-horse-1"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def register(c: AsyncClient, email: str = "ann@example.com", name: str = "Ann") -> dict[str, Any]:
    r = await c.post("/api/v1/auth/register", json={"username": name, "email": email, "password": PW})
    assert r.status_code == 201, r.text
    c.headers["X-CSRF-Token"] = c.cookies["csrf_token"]
    return r.json()  # type: ignore[no-any-return]


async def test_register_login_me_logout(client: AsyncClient) -> None:
    u = await register(client)
    assert u["username"] == "Ann" and u["agent_count"] == 0
    assert (await client.get("/api/v1/auth/me")).json()["uid"] == u["uid"]
    await client.post("/api/v1/auth/logout")
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.post("/api/v1/auth/login", json={"email": "ann@example.com", "password": "wrong-password"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "no@example.com", "password": "wrong-password"})
    assert (
        bad.status_code == unknown.status_code == 401
        and bad.json()["error"]["message"] == unknown.json()["error"]["message"]
    )
    ok = await client.post("/api/v1/auth/login", json={"email": "ANN@example.com", "password": PW})
    assert ok.status_code == 200 and ok.json()["uid"] == u["uid"]


async def test_register_validation_and_duplicate(client: AsyncClient) -> None:
    await register(client)
    dup = await client.post(
        "/api/v1/auth/register", json={"username": "Ann2", "email": "ann@example.com", "password": PW}
    )
    assert dup.status_code == 409
    short = await client.post(
        "/api/v1/auth/register", json={"username": "Bo", "email": "bo@example.com", "password": "short"}
    )
    assert short.status_code == 422


async def test_password_not_stored_plaintext(client: AsyncClient, app_and_sm: Any) -> None:
    from sqlalchemy import select

    from app.db.models import User

    await register(client)
    _, sm = app_and_sm
    async with sm() as s:
        u = (await s.scalars(select(User))).one()
    assert u.password_hash and PW not in u.password_hash and u.password_hash.startswith("$argon2")


async def test_tampered_and_expired_tokens_rejected(client: AsyncClient) -> None:
    u = await register(client)
    good = client.cookies["access_token"]
    s = get_settings()
    forged = jwt.encode(
        {"sub": u["uid"], "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1)},
        "x" * 32,
        algorithm="HS256",
    )
    expired = jwt.encode(
        {"sub": u["uid"], "iat": datetime.now(UTC) - timedelta(hours=2), "exp": datetime.now(UTC) - timedelta(hours=1)},
        s.auth_jwt_secret,
        algorithm="HS256",
    )
    for bad in (forged, expired, good[:-3] + "abc", "garbage"):
        client.cookies.set("access_token", bad)
        assert (await client.get("/api/v1/auth/me")).status_code == 401
    client.cookies.set("access_token", good)
    assert (await client.get("/api/v1/auth/me")).status_code == 200


async def test_uid_mismatch_is_403_and_csrf_enforced(client: AsyncClient, other_client: AsyncClient) -> None:
    a = await register(client)
    b = await register(other_client, "bob@example.com", "Bob")
    assert (await client.get(f"/api/v1/users/{b['uid']}")).status_code == 403
    assert (await client.get(f"/api/v1/users/{a['uid']}/agents")).status_code == 200
    del client.headers["X-CSRF-Token"]
    r = await client.post(f"/api/v1/users/{a['uid']}/agents", json={"name": "X", "role_behavior": "does things well"})
    assert r.status_code == 403


async def _make_agent(c: AsyncClient, uid: str, name: str = "Ava") -> str:
    r = await c.post(f"/api/v1/users/{uid}/agents", json={"name": name, "role_behavior": "Books dental appointments"})
    assert r.status_code == 201
    return r.json()["aid"]  # type: ignore[no-any-return]


async def test_agent_payment_flow(client: AsyncClient) -> None:
    u = await register(client)
    base = f"/api/v1/users/{u['uid']}/agents"
    aid = await _make_agent(client, u["uid"])
    assert (await client.get(base)).json() == []  # pending agents are hidden
    for amount in (99, 100.5, 0):
        r = await client.post(f"{base}/{aid}/payment", json={"amount": amount})
        assert r.status_code == 402
    assert (await client.get(base)).json() == []
    ok = await client.post(f"{base}/{aid}/payment", json={"amount": 100})
    assert ok.status_code == 200 and ok.json()["lifecycle"] == "ACTIVE"
    listed = (await client.get(base)).json()
    assert [a["name"] for a in listed] == ["Ava"] and listed[0]["status"] == "free"
    assert (await client.post(f"{base}/{aid}/payment", json={"amount": 100})).status_code == 409
    assert (await client.get("/api/v1/auth/me")).json()["agent_count"] == 1


async def test_agent_update_and_ownership(client: AsyncClient, other_client: AsyncClient) -> None:
    a = await register(client)
    b = await register(other_client, "bob@example.com", "Bob")
    aid = await _make_agent(client, a["uid"])
    await client.post(f"/api/v1/users/{a['uid']}/agents/{aid}/payment", json={"amount": 100})
    r = await client.put(
        f"/api/v1/users/{a['uid']}/agents/{aid}", json={"name": "Ava2", "role_behavior": "Now handles cancellations"}
    )
    assert r.status_code == 200 and r.json()["name"] == "Ava2"
    assert (await client.get(f"/api/v1/users/{a['uid']}/agents")).json()[0]["role_behavior"].startswith("Now handles")
    # Bob cannot reach Ava's agent, even through his own uid
    steal = await other_client.put(
        f"/api/v1/users/{b['uid']}/agents/{aid}", json={"name": "Mine", "role_behavior": "Stolen agent role"}
    )
    assert steal.status_code == 404
    assert (
        await other_client.post(f"/api/v1/users/{b['uid']}/agents/{aid}/payment", json={"amount": 100})
    ).status_code == 404
    assert (await other_client.get(f"/api/v1/users/{b['uid']}/agents")).json() == []


async def test_avatar_upload(client: AsyncClient) -> None:
    u = await register(client)
    url = f"/api/v1/users/{u['uid']}/avatar"
    assert (await client.get(url)).status_code == 404
    bad = await client.put(url, content=b"not an image", headers={"content-type": "image/png"})
    assert bad.status_code == 422
    big = await client.put(url, content=PNG + b"0" * (2 * 1024 * 1024))
    assert big.status_code == 422
    ok = await client.put(url, content=PNG, headers={"content-type": "image/png"})
    assert ok.status_code == 200 and ok.json()["avatar_url"].startswith(url)
    got = await client.get(url)
    assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"


async def test_manager_prompt_lists_agents_and_call_is_linked(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    u = await register(client)
    await client.post(
        f"/api/v1/users/{u['uid']}/agents/{await _make_agent(client, u['uid'])}/payment", json={"amount": 100}
    )
    m = await client.get(f"/api/v1/users/{u['uid']}/manager")
    assert m.status_code == 200
    r = await client.post(f"/api/v1/users/{u['uid']}/manager/calls")
    assert r.status_code == 200, r.text
    cid = r.json()["call_id"]
    listed = (await client.get(f"/api/v1/users/{u['uid']}/manager/calls")).json()
    assert [c["id"] for c in listed] == [cid]
    from tests.conftest import INTERNAL

    ctx = (await client.get(f"/internal/calls/{cid}/context", headers=INTERNAL)).json()
    prompt = ctx["profile"]["context_prompt"]
    assert "Ava" in prompt and "free" in prompt
    # existing per-call endpoint works for the owner through their workspace
    assert (await client.get(f"/api/v1/calls/{cid}")).status_code == 200
    uuid.UUID(cid)


async def test_calls_isolated_between_users(client: AsyncClient, other_client: AsyncClient) -> None:
    a = await register(client)
    await register(other_client, "bob@example.com", "Bob")
    cid = (await client.post(f"/api/v1/users/{a['uid']}/manager/calls")).json()["call_id"]
    assert (await other_client.get(f"/api/v1/calls/{cid}")).status_code == 404
