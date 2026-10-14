# Architecture (current)
- `frontend` (React/Redux/RTK Query) → `/api/v1` on `backend` (FastAPI). nginx blocks `/internal` and `/metrics`.
- `POST /calls` snapshots the active profile version, mints a short-lived LiveKit token whose room config
  dispatches the named agent with `{call_id, correlation_id}` metadata.
- `agent` worker fetches `/internal/calls/{id}/context`, composes instructions (guardrails → client prompt →
  runtime), runs `AgentSession`, persists each finalized turn, and on shutdown posts a schema-validated summary.
  If that fails, the backend fallback summarizer (and a periodic sweeper) builds it from persisted turns.
- Transcripts reach the browser over the `lk.transcription` text stream; the Room lives outside Redux.
