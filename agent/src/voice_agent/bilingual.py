"""Speaks each reply in a voice that can say it: English in the agent's own voice, Hindi in a Hindi voice.

The caller's language is detected by speech recognition (STT_LANGUAGE=multi) and the model answers in that language,
writing Hindi in Devanagari. The script of the reply is therefore what decides the voice, so the voice can never
disagree with the words.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator
from typing import Any

from livekit import rtc
from livekit.agents import Agent, tts, utils

# Letters read before choosing a voice: enough to see past a leading English word or name ("Vishnu जी, ..."), few
# enough to arrive in the first chunks of a reply.
PEEK_LETTERS = 12


def is_hindi(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


async def peek_language(text: AsyncIterable[str]) -> tuple[bool, AsyncIterator[str]]:
    """Reads just enough of `text` to tell whether it is Hindi; returns that and the whole text, nothing lost."""
    it = aiter(text)
    head: list[str] = []
    async for chunk in it:
        head.append(chunk)
        seen = "".join(head)
        if is_hindi(seen) or sum(ch.isalpha() for ch in seen) >= PEEK_LETTERS:
            break

    async def whole() -> AsyncIterator[str]:
        for chunk in head:
            yield chunk
        async for chunk in it:
            yield chunk

    return is_hindi("".join(head)), whole()


class BilingualAgent(Agent):
    def __init__(self, *, hindi_tts: tts.TTS | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.hindi_tts = hindi_tts

    async def on_enter(self) -> None:
        if self.hindi_tts is not None:
            self.hindi_tts.prewarm()

    async def tts_node(self, text: AsyncIterable[str], model_settings: Any) -> AsyncGenerator[rtc.AudioFrame, None]:
        hindi, text = await peek_language(text)
        if not hindi or self.hindi_tts is None:
            async for frame in Agent.default.tts_node(self, text, model_settings):
                yield frame
            return
        async with self.hindi_tts.stream() as stream:

            async def forward() -> None:
                async for chunk in text:
                    stream.push_text(chunk)
                stream.end_input()

            task = asyncio.create_task(forward())
            try:
                async for ev in stream:
                    yield ev.frame
            finally:
                await utils.aio.cancel_and_wait(task)
