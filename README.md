# Voice Agent Platform (LiveKit)

Profile-driven real-time voice agents: describe a role in the web UI, talk to it in the browser, get a
structured post-call summary. STT → LLM → TTS pipeline (Deepgram → Gemini → Deepgram) on LiveKit Cloud.

## Status
| Phase | State |
|---|---|
| 1 Foundation | Done, verified (compose stack, migrations, tests) |
| 2 Core voice + Web UI | Working end to end (browser call, live transcript, post-call summary, chat titles) |
| 3–6 | Not started |

Latency is measured per turn but not yet tuned (about 1.6–1.9 s from end of speech to the agent's reply; the
target is under 800 ms). See `docs/adr/` for decisions.

## Requirements

### System tools
| Tool | Version used | Needed for |
|---|---|---|
| Git | any recent | cloning |
| [uv](https://docs.astral.sh/uv/) | 0.13+ | Python envs and lockfiles (it can fetch Python 3.12+ itself) |
| Python | 3.12 or newer (developed on 3.13) | backend and agent (`livekit-agents` requires >=3.12) |
| Node.js + npm | 22 LTS | frontend |
| Docker + Docker Compose | 29.x | Postgres, Redis, and the full containerised stack |
| `psql` (optional) | 16+ | inspecting the database |
| `make` | any | shortcuts in the `Makefile` |

### Accounts and API keys (put them in `.env`, never commit it)
| Service | Variable(s) | Used for |
|---|---|---|
| [LiveKit Cloud](https://cloud.livekit.io) | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | real-time audio rooms, agent dispatch, noise cancellation |
| [Google AI Studio (Gemini)](https://aistudio.google.com) | `GEMINI_API_KEY` | agent LLM, role-prompt generation, call summaries |
| [Deepgram](https://deepgram.com) | `DEEPGRAM_API_KEY` | speech-to-text and text-to-speech |

Also set `INTERNAL_API_TOKEN` and `WORKSPACE_COOKIE_SECRET` (any random strings of 16+ characters).
Gemini model names change often: check which ones your key can use, then set `GEMINI_TEXT_MODEL`,
`AGENT_LLM_MODEL` and `GEMINI_FALLBACK_MODELS` in `.env`.

### Backend (`backend/`, Python)
`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `redis`, `httpx`,
`prometheus-client`, `google-genai`, `jsonschema`, `itsdangerous`, `slowapi`, `livekit-api`.
Dev: `pytest`, `pytest-asyncio`, `aiosqlite`, `ruff`, `mypy`, `types-jsonschema`.

### Agent worker (`agent/`, Python)
`livekit-agents` 1.8.x with plugins `livekit-plugins-silero` (VAD), `livekit-plugins-google` (Gemini),
`livekit-plugins-deepgram` (STT and TTS), `livekit-plugins-turn-detector`, `livekit-plugins-noise-cancellation`,
plus `livekit-api`, `httpx`, `jsonschema`, `pydantic`, `pydantic-settings`.
Dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

### Frontend (`frontend/`, Node)
Runtime: `react` 18, `react-dom`, `react-router-dom`, `@reduxjs/toolkit`, `react-redux`, `livekit-client`,
`@livekit/components-react`, `three`, `@react-three/fiber` 8.
Dev: `typescript`, `vite`, `@vitejs/plugin-react`, `vitest`, `jsdom`, `@testing-library/*`, `eslint`,
`typescript-eslint`, `eslint-plugin-react-hooks`, `prettier`, `@playwright/test`.

### Ports used
| Port | What |
|---|---|
| 5173 | frontend dev server |
| 8000 | backend API |
| 5443 | dev Postgres (container port 5432) |
| 6390 | dev Redis (container port 6379) |
| 8080 | frontend in the full Docker stack |

### Install everything
```bash
cd backend  && uv sync                 # Python deps from uv.lock
cd ../agent && uv sync
cd agent && uv run python -m voice_agent.worker download-files   # one-time: VAD / turn-detector model weights
cd ../frontend && npm ci               # Node deps from package-lock.json
```
A browser with microphone access is needed to talk to the agent (tested in Chrome).

## Run
1. `cp .env.example .env` and fill: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GEMINI_API_KEY`,
   `DEEPGRAM_API_KEY`, `INTERNAL_API_TOKEN`, `WORKSPACE_COOKIE_SECRET` (the last two: any 16+ random chars).
2. Everything in containers: `make up` → UI on http://localhost:8080.
   (In local dev set `BACKEND_INTERNAL_URL=http://localhost:8000`; compose overrides it to `http://backend:8000`.)
3. Or local dev: `make dev` (Postgres/Redis + migrations), then in three terminals:
   - `cd backend && uv run uvicorn app.main:create_app --factory --reload`
   - `cd agent && uv run python -m voice_agent.worker dev`
   - `cd frontend && npm run dev` → http://localhost:5173

## Test
`make test` (backend + agent), `cd frontend && npm test -- --run`, `make lint`.
