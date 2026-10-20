import os
import tempfile

os.environ.update(
    AUTH_JWT_SECRET="test-auth-jwt-secret-0123456789abcdef",
    RATE_LIMIT_AUTH="1000/minute",
    RATE_LIMIT_PUBLIC="1000/minute",
    UPLOAD_DIR=tempfile.mkdtemp(prefix="rtva-test-uploads-"),
    ENV="test",
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    INTERNAL_API_TOKEN="test-internal-token-123456",
    WORKSPACE_COOKIE_SECRET="test-cookie-secret-123456",
    LIVEKIT_URL="wss://example.livekit.cloud",
    LIVEKIT_API_KEY="APItestkey",
    LIVEKIT_API_SECRET="test-livekit-secret-0123456789abcdef0123",
)

import copy
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.agent_profiles import get_generator
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

FAKE_FIELDS: dict[str, Any] = {
    "agent_name": "Ava",
    "role_summary": "Appointment reminder agent for Dr. Smith's clinic",
    "objective": "Remind patients of upcoming appointments",
    "persona_and_tone": "Warm, brief",
    "language_and_voice_style": "Plain English, short sentences",
    "conversation_flow": {
        "opening": "Hi, this is Ava.",
        "main_steps": ["Confirm identity", "Remind"],
        "closing": "Goodbye.",
    },
    "in_scope_topics": ["appointment time"],
    "out_of_scope_topics_and_deflection_style": "Politely decline and steer back.",
    "escalation_rules": "Offer a callback from staff.",
    "information_to_collect": ["confirmation"],
    "hard_rules": ["Never give medical advice"],
    "factual_grounding_policy": "Only state facts you were given. Clinic hours: [CLIENT-PROVIDED: clinic hours]",
    "call_ending_conditions": ["Appointment confirmed"],
    "assumptions_made": ["Calls are in English"],
}


class FakeGenerator:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []

    async def generate_json(self, *, system: str, user: str, schema: Any, temperature: float) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user})
        if self.responses:
            return self.responses.pop(0)
        return copy.deepcopy(FAKE_FIELDS)


@pytest.fixture
def fake_gen() -> FakeGenerator:
    return FakeGenerator()


@pytest_asyncio.fixture
async def app_and_sm(fake_gen: FakeGenerator) -> AsyncIterator[Any]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _session() -> AsyncIterator[Any]:
        async with sm() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_generator] = lambda: fake_gen
    yield app, sm
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app_and_sm: Any) -> AsyncIterator[AsyncClient]:
    app, _ = app_and_sm
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def other_client(app_and_sm: Any) -> AsyncIterator[AsyncClient]:
    app, _ = app_and_sm
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


INTERNAL = {"Authorization": "Bearer test-internal-token-123456"}
