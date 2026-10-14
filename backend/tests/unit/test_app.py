import pytest
from fastapi.testclient import TestClient

from app.core.config import ConfigError, Settings, get_settings
from app.main import create_app


def test_healthz_and_correlation_header():
    client = TestClient(create_app())
    r = client.get("/healthz", headers={"X-Correlation-ID": "abc123"})
    assert r.status_code == 200 and r.headers["X-Correlation-ID"] == "abc123"
    assert client.get("/api/v1/healthz").status_code == 200
    assert b"http_requests_total" in client.get("/metrics").content


def test_missing_config_lists_names_only(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env on disk
    monkeypatch.delenv("LIVEKIT_API_SECRET")
    monkeypatch.delenv("INTERNAL_API_TOKEN")
    get_settings.cache_clear()
    with pytest.raises(ConfigError) as e:
        get_settings()
    assert "LIVEKIT_API_SECRET" in str(e.value) and "INTERNAL_API_TOKEN" in str(e.value)
    assert "test-" not in str(e.value)
    get_settings.cache_clear()


def test_settings_class_importable():
    assert Settings.model_fields["agent_name"].default == "voice-agent"
