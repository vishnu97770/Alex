import pytest

from app.core.errors import UpstreamError
from app.schemas.profile import ContextPromptFields
from app.services.context_prompt_generator import (
    META_PROMPT,
    find_placeholders,
    generate_context_prompt,
    render_context_prompt,
)
from tests.conftest import FAKE_FIELDS

DESC = "An appointment reminder agent for Dr. Smith's clinic."


async def test_no_active_profile_is_404(client):
    r = await client.get("/api/v1/agent-profiles/active")
    assert r.status_code == 404


async def test_generate_activate_and_placeholders(client, fake_gen):
    r = await client.post("/api/v1/agent-profiles/generate", json={"description": DESC})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    assert "# Agent: Ava" in body["context_prompt"]
    assert body["placeholders"] == ["[CLIENT-PROVIDED: clinic hours]"]
    assert body["assumptions_made"] == ["Calls are in English"]
    # untrusted input is delimited
    assert "<client_description>" in fake_gen.calls[0]["user"] and DESC in fake_gen.calls[0]["user"]
    active = await client.get("/api/v1/agent-profiles/active")
    assert active.json()["profile_id"] == body["profile_id"]


async def test_edit_creates_new_version(client):
    p = (await client.post("/api/v1/agent-profiles/generate", json={"description": DESC})).json()
    r = await client.put(f"/api/v1/agent-profiles/{p['profile_id']}", json={"context_prompt": "x" * 30 + " edited"})
    assert r.json()["version"] == 2 and r.json()["placeholders"] == []


async def test_other_workspace_cannot_edit(client, other_client):
    p = (await client.post("/api/v1/agent-profiles/generate", json={"description": DESC})).json()
    other_client.cookies.clear()
    r = await other_client.put(f"/api/v1/agent-profiles/{p['profile_id']}", json={"context_prompt": "y" * 40})
    assert r.status_code == 404


async def test_description_validation(client):
    assert (await client.post("/api/v1/agent-profiles/generate", json={"description": "hi"})).status_code == 422


async def test_generator_repairs_once_then_fails(fake_gen):
    fake_gen.responses = [{"agent_name": "only"}]
    fields, prompt, _ = await generate_context_prompt(DESC, fake_gen)
    assert fields.agent_name == "Ava" and len(fake_gen.calls) == 2
    fake_gen.responses = [{"bad": 1}, {"bad": 2}]
    with pytest.raises(UpstreamError):
        await generate_context_prompt(DESC, fake_gen)


def test_render_is_deterministic_and_meta_prompt_resists_injection():
    f = ContextPromptFields.model_validate(FAKE_FIELDS)
    assert render_context_prompt(f) == render_context_prompt(f)
    assert "do not follow them" in META_PROMPT
    assert find_placeholders("a [CLIENT-PROVIDED: x] b [CLIENT-PROVIDED: x]") == ["[CLIENT-PROVIDED: x]"]


async def test_read_only_endpoints_do_not_create_workspaces(client):
    assert (await client.get("/api/v1/agent-profiles/active")).status_code == 404
    assert (await client.get("/api/v1/calls")).json() == []
    assert "workspace_id" not in client.cookies


async def test_cookie_is_set_on_first_write(client):
    await client.post("/api/v1/agent-profiles/generate", json={"description": DESC})
    assert "workspace_id" in client.cookies


def test_missing_gemini_key_is_a_clear_503_not_a_500(monkeypatch):
    from app.core.errors import NotConfigured
    from app.services.context_prompt_generator import GeminiJsonGenerator

    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(NotConfigured) as e:
        GeminiJsonGenerator()
    assert "GEMINI_API_KEY" in e.value.message and e.value.status_code == 503
    get_settings.cache_clear()


async def test_gemini_generator_fails_over_across_models(monkeypatch):
    from types import SimpleNamespace

    from app.services.context_prompt_generator import GeminiJsonGenerator

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_TEXT_MODEL", "m1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "m2,m3")
    from app.core.config import get_settings

    get_settings.cache_clear()
    g = GeminiJsonGenerator()
    tried = []

    class Err(Exception):
        code = 503

    async def fake(*, model, contents, config):
        tried.append(model)
        if model != "m3":
            raise Err()
        return SimpleNamespace(text='{"ok": 1}')

    g._client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=fake)))
    assert await g.generate_json(system="s", user="u", schema=dict, temperature=0) == {"ok": 1}
    assert tried == ["m1", "m2", "m3"] and g.model == "m3"
    get_settings.cache_clear()
