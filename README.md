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

### Install the system tools

**Ubuntu / Debian Linux**
```bash
sudo apt update && sudo apt install -y git make curl postgresql-client

# uv (Python package/env manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 22 via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc && nvm install 22

# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # then log out and back in
```

**macOS (Homebrew)**
```bash
brew install git make uv node@22 libpq
brew install --cask docker          # Docker Desktop; open it once so the daemon starts
```

**Windows**: use WSL2 and follow the Ubuntu steps inside it (`wsl --install -d Ubuntu`, then install Docker
Desktop with the WSL2 backend). Native alternative:
```powershell
winget install Git.Git astral-sh.uv OpenJS.NodeJS.LTS Docker.DockerDesktop
```
(`make` is not available natively on Windows; run the commands from the `Makefile` by hand or use WSL.)

Check everything is installed:
```bash
git --version && uv --version && node -v && npm -v && docker --version && docker compose version && make --version
```
You do not need to install Python yourself: `uv sync` downloads Python 3.12+ if it is missing.

### Install the project
```bash
git clone <your-repo-url> voice-agent-platform
cd voice-agent-platform

# 1. Python dependencies (creates backend/.venv and agent/.venv from the lockfiles)
(cd backend && uv sync)
(cd agent && uv sync)

# 2. One-time download of the voice model weights (VAD + turn detector)
(cd agent && uv run python -m voice_agent.worker download-files)

# 3. Frontend dependencies
(cd frontend && npm ci)

# 4. Configuration: copy the template, then fill in your keys (see "Accounts and API keys")
cp .env.example .env
sed -i "s|^INTERNAL_API_TOKEN=.*|INTERNAL_API_TOKEN=$(openssl rand -hex 24)|; s|^WORKSPACE_COOKIE_SECRET=.*|WORKSPACE_COOKIE_SECRET=$(openssl rand -hex 24)|" .env
#   then edit .env: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, GEMINI_API_KEY, DEEPGRAM_API_KEY
ln -sf ../.env backend/.env && ln -sf ../.env agent/.env   # lets each service find the shared .env

# 5. Start Postgres + Redis (Docker) and create the database tables
make infra
(cd backend && uv run alembic upgrade head)
```
On macOS use `sed -i ''` instead of `sed -i`. Now continue with **Run** below.

## Run
1. Complete **Install the project** above (dependencies, `.env` with your keys, Postgres/Redis, migrations).
2. Everything in containers: `make up` → UI on http://localhost:8080.
   (In local dev set `BACKEND_INTERNAL_URL=http://localhost:8000`; compose overrides it to `http://backend:8000`.)
3. Or local dev: `make dev` (Postgres/Redis + migrations), then in three terminals:
   - `cd backend && uv run uvicorn app.main:create_app --factory --reload`
   - `cd agent && uv run python -m voice_agent.worker dev`
   - `cd frontend && npm run dev` → http://localhost:5173

## Test
`make test` (backend + agent), `cd frontend && npm test -- --run`, `make lint`.

## Web app: accounts, agents, manager

Routes: `/home` (the landing page, `frontend/src/pages/Landing.jsx`; always shown; signed-in visitors see "Open app" in its nav, others use Sign in / Sign up which go to `/checkin`), `/checkin`, `/dashboard/:uid`,
`/agents/:uid`, `/create_agent/:uid`, `/create_agent/:uid/:aid` (simulated payment, amount `100`), `/agents/:uid/update/:aid`,
`/manager/:uid` (+ `/manager/:uid/chats/:id`), `/profile/:uid`, `/settings/:uid`.  The landing page's components and CSS live in `frontend/src/components/landing/` (taken from github.com/vishnu97770/Real-Time-Voice-Agent).

Auth: email + password (argon2) and Google. The session is an httpOnly JWT cookie plus a CSRF cookie echoed in `X-CSRF-Token`.
Set `AUTH_JWT_SECRET` in `.env`. Google sign-in stays disabled until `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` are set; create a
Web OAuth client in Google Cloud Console and add `http://localhost:5173/api/v1/auth/google/callback` as an authorised redirect URI.

Run order: `make infra`, `cd backend && uv run alembic upgrade head` (migration `0002` adds `users`, `agents`, `managers`,
`agent_payments`, `call_links`; existing tables are untouched), then backend, agent and frontend as above.
