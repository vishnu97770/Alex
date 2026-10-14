import os

os.environ.update(
    ENV="test",
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    INTERNAL_API_TOKEN="test-internal-token-123456",
    WORKSPACE_COOKIE_SECRET="test-cookie-secret-123456",
    LIVEKIT_URL="wss://example.livekit.cloud",
    LIVEKIT_API_KEY="APItestkey",
    LIVEKIT_API_SECRET="test-livekit-secret-0123456789abcdef0123",
)
