from livekit.agents import vad
from livekit.plugins import silero


def load_vad() -> vad.VAD:
    """Loaded once in process prewarm; telephony audio is 8k-ish so 16k model input is fine."""
    return silero.VAD.load()
