"""Post-call summary from the transcript: schema-validated with a single repair retry."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import jsonschema

from voice_agent.config import AgentSettings

log = logging.getLogger("summarizer")


def _contracts_dir() -> Path:
    for p in (Path(__file__).resolve().parents[4] / "contracts", Path("/app/contracts")):
        if (p / "call-summary.schema.json").exists():
            return p
    raise FileNotFoundError("contracts directory not found")


def load_contract() -> tuple[dict[str, Any], str]:
    d = _contracts_dir()
    return json.loads((d / "call-summary.schema.json").read_text()), (d / "summary_prompt.txt").read_text()


def format_transcript(turns: list[dict[str, Any]]) -> str:
    return "\n".join(f"{t['speaker'].upper()}: {t['text']}" for t in turns if t.get("is_final", True))


class GeminiSummarizer:
    def __init__(self, s: AgentSettings):
        from google import genai

        self.model = s.gemini_text_model
        self._client = genai.Client(api_key=s.gemini_api_key)

    async def generate(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        from google.genai import types

        resp = await self._client.aio.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
                response_mime_type="application/json",
                response_json_schema=schema,
            ),
        )
        out: dict[str, Any] = json.loads(resp.text or "")
        return out


async def summarize(
    turns: list[dict[str, Any]], generator: Any, *, extensions: dict[str, str] | None = None
) -> dict[str, Any]:
    """`generator.generate(system, user, schema) -> dict`. Raises on persistent failure."""
    schema, prompt = load_contract()
    if extensions:
        prompt += "\nAlso include these extra top-level fields: " + json.dumps(extensions)
    user = f"<transcript>\n{format_transcript(turns)}\n</transcript>"
    err: str | None = None
    for attempt in range(2):
        u = user if attempt == 0 else f"{user}\n\nYour previous output was invalid ({err}). Fix it."
        try:
            raw = await generator.generate(prompt, u, schema)
            jsonschema.validate(raw, schema)
            return raw  # type: ignore[no-any-return]
        except (jsonschema.ValidationError, json.JSONDecodeError) as e:
            err = str(getattr(e, "message", e))[:200]
            log.warning("summary invalid", extra={"attempt": attempt + 1})
    raise ValueError(f"summary failed validation: {err}")


async def summarize_with_timeout(
    turns: list[dict[str, Any]], generator: Any, timeout: float, **kw: Any
) -> dict[str, Any]:
    return await asyncio.wait_for(summarize(turns, generator, **kw), timeout)
