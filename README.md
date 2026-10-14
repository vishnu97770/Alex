# Voice Agent Platform (LiveKit)

Profile-driven real-time voice agents: describe a role in the web UI, talk to it in the browser, get a
structured post-call summary. STT → LLM → TTS pipeline (Deepgram → Gemini → Deepgram) on LiveKit Cloud.

## Status
| Phase | State |
|---|---|
| 1 Foundation | Done, verified (compose stack, migrations, tests) |
| 2 Core voice + Web UI | **Code complete and unit-tested; live end-to-end call NOT yet run** (needs real keys) |
| 3–6 | Not started |

Nothing latency-related has been measured yet. See `docs/adr/` for decisions.

## Run
1. `cp .env.example .env` and fill: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GEMINI_API_KEY`,
   `DEEPGRAM_API_KEY`, `INTERNAL_API_TOKEN`, `WORKSPACE_COOKIE_SECRET` (the last two: any 16+ random chars).
2. Everything in containers: `make up` → UI on http://localhost:8080.
3. Or local dev: `make dev` (Postgres/Redis + migrations), then in three terminals:
   - `cd backend && uv run uvicorn app.main:create_app --factory --reload`
   - `cd agent && uv run python -m voice_agent.worker dev`
   - `cd frontend && npm run dev` → http://localhost:5173

## Test
`make test` (backend + agent), `cd frontend && npm test -- --run`, `make lint`.
