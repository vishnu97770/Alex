"""Agent -> backend internal API client (bearer token, bounded retries, no secret logging)."""

import asyncio
import logging
from typing import Any

import httpx

log = logging.getLogger("backend_client")


class BackendClient:
    def __init__(self, base_url: str, token: str, *, correlation_id: str = "", retries: int = 3):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": correlation_id},
            timeout=httpx.Timeout(10.0),
        )
        self._retries = retries

    async def _request(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        delay = 0.3
        last: Exception | None = None
        for attempt in range(self._retries):
            try:
                r = await self._http.request(method, path, **kw)
                if r.status_code < 500 and r.status_code != 429:
                    r.raise_for_status()
                    out: dict[str, Any] = r.json()
                    return out
                last = httpx.HTTPStatusError("server error", request=r.request, response=r)
            except httpx.TransportError as e:
                last = e
            log.warning("backend call failed", extra={"path": path, "attempt": attempt + 1})
            await asyncio.sleep(delay)
            delay *= 2
        assert last is not None
        raise last

    async def get_context(self, call_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/internal/calls/{call_id}/context")

    async def post_turns(self, call_id: str, turns: list[dict[str, Any]]) -> None:
        await self._request("POST", f"/internal/calls/{call_id}/turns", json={"turns": turns})

    async def post_event(self, call_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        await self._request(
            "POST", f"/internal/calls/{call_id}/events", json={"type": event_type, "payload": payload or {}}
        )

    async def post_summary(self, call_id: str, body: dict[str, Any]) -> None:
        await self._request("POST", f"/internal/calls/{call_id}/summary", json=body)

    async def request_fallback_summary(self, call_id: str) -> None:
        await self._request("POST", f"/internal/calls/{call_id}/summary/fallback")

    async def aclose(self) -> None:
        await self._http.aclose()
