import os

os.environ.update(
    INTERNAL_API_TOKEN="test-internal-token-123456",
    LIVEKIT_URL="wss://example.livekit.cloud",
    LIVEKIT_API_KEY="APItest",
    LIVEKIT_API_SECRET="secret-secret-secret-secret-0123456789",
    GEMINI_API_KEY="fake-gemini",
    DEEPGRAM_API_KEY="fake-deepgram",
    ENABLE_NOISE_CANCELLATION="false",
    TURN_DETECTION="vad",
)
