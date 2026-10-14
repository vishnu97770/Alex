"""Persist finalized conversation items incrementally (not at shutdown)."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from voice_agent.backend_client import BackendClient

log = logging.getLogger("transcript")
_METRIC_KEYS = (
    "end_of_turn_delay",
    "transcription_delay",
    "llm_node_ttft",
    "tts_node_ttfb",
    "e2e_latency",
    "started_speaking_at",
    "stopped_speaking_at",
)


def item_to_turn(item: Any, seq: int) -> dict[str, Any] | None:
    if getattr(item, "type", None) != "message" or item.role not in ("user", "assistant"):
        return None
    text = (item.text_content or "").strip()
    if not text:
        return None
    m = dict(getattr(item, "metrics", None) or {})
    metrics = {k: m[k] for k in _METRIC_KEYS if k in m}
    if getattr(item, "interrupted", False):
        metrics["interrupted"] = True
    return {
        "seq": seq,
        "speaker": "user" if item.role == "user" else "agent",
        "text": text,
        "is_final": True,
        "started_at": datetime.fromtimestamp(m["started_speaking_at"], UTC).isoformat()
        if "started_speaking_at" in m
        else None,
        "ended_at": datetime.fromtimestamp(m["stopped_speaking_at"], UTC).isoformat()
        if "stopped_speaking_at" in m
        else None,
        "metrics_json": metrics,
    }


class TranscriptRecorder:
    def __init__(self, backend: BackendClient, call_id: str):
        self._backend, self._call_id = backend, call_id
        self._seq = 0
        self._seen: set[str] = set()
        self.turns: list[dict[str, Any]] = []
        self._q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    def attach(self, session: Any) -> None:
        session.on("conversation_item_added", self._on_item)
        self._task = asyncio.create_task(self._pump())

    def _on_item(self, ev: Any) -> None:
        item = ev.item
        item_id = getattr(item, "id", None)
        if item_id and item_id in self._seen:  # duplicate event
            return
        turn = item_to_turn(item, self._seq)
        if turn is None:
            return
        if item_id:
            self._seen.add(item_id)
        self._seq += 1
        self.turns.append(turn)
        self._q.put_nowait(turn)

    async def _pump(self) -> None:
        while True:
            turn = await self._q.get()
            try:
                await self._backend.post_turns(self._call_id, [turn])
            except Exception:
                log.exception("turn persist failed", extra={"call_id": self._call_id, "seq": turn["seq"]})
            finally:
                self._q.task_done()

    async def flush(self, timeout: float = 8.0) -> None:
        try:
            await asyncio.wait_for(self._q.join(), timeout)
        except TimeoutError:
            log.warning("transcript flush timed out", extra={"call_id": self._call_id})
        if self._task:
            self._task.cancel()
