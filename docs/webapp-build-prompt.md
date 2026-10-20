# Build prompt: turn the Voice Agent into a full web application

> Paste this whole file as the first message of a fresh Claude Code session in `/home/hp/Desktop/RTVA`.

## 0. Your role

You are a senior full-stack engineer extending the existing **RTVA Voice Agent** project into a complete,
multi-user, authenticated web application. Work inside the existing repo and match its conventions
(comment density, naming, idioms). Be accurate: **do not invent files, APIs, columns or behaviour.**
If something below is ambiguous, or something you need is missing (for example Google OAuth credentials),
state the assumption explicitly or ask. Never silently guess.

Before writing code, read the repo and confirm the facts in section 1. Then present a short plan and wait
for approval if the plan deviates from this document.

## 1. Current state (verify, don't assume)

- `backend/` is FastAPI + SQLAlchemy (async, asyncpg) + Alembic (`backend/alembic/versions/0001_initial_core_schema.py`).
  Models live in `backend/app/db/models/core.py`: `Workspace`, `AgentProfile`, `AgentProfileVersion`, `Call`,
  `CallTurn`, `CallSummary`, `AuditEvent`. Routes are in `backend/app/api/v1/` (`agent_profiles.py`,
  `calls.py`, `health.py`, `internal.py`). Identity today is an anonymous signed cookie `workspace_id`
  (`backend/app/core/security.py`, `backend/app/api/deps.py::get_workspace_id`). The docstring there says it is
  meant to be swapped for real auth.
- `agent/` is the LiveKit voice-agent worker (`agent/src/voice_agent/`), which fetches profiles from the backend.
- `frontend/` is **React + Vite, plain JavaScript (`.jsx`/`.js`)**. It was converted from TypeScript.
  Do not reintroduce TypeScript. It uses Redux Toolkit (`app/store.js`, `features/*`), RTK Query (`api/api.js`),
  `react-router-dom` v7 (`app/router.jsx`, currently `/`, `/call`, `/chats/:id`, `/settings` under `components/Layout`),
  LiveKit client, a Three.js `Sphere`, `ChatBox`, `Sidebar`, `SummaryCard`/`SummaryPanel`, and `ChatPage.jsx`
  (call list on the left, transcript and sphere in the middle, summary on the right).
- Postgres runs from `docker-compose.dev.yml` (host port 5443, db/user/password `voice`). `make infra` starts it.
  Config comes from `backend/.env` (`DATABASE_URL`, `WORKSPACE_COOKIE_SECRET`, `APP_ORIGIN`, and so on).
- Tests: backend `backend/tests`, agent `agent/tests`, frontend vitest (`npm test -- --run`), CI in
  `.github/workflows/ci.yml`.

## 2. Hard constraints

1. **Do not modify the existing call/transcript/summary schema.** Existing tables and columns stay as they are;
   they store calls, transcripts and summaries correctly. Add new tables only, through a **new Alembic migration**
   (`0002_...`). Do not edit `0001`. Existing rows and existing endpoints must keep working.
2. **Do not break the current voice flow** (token minting, LiveKit rooms, the agent worker, summaries, the sweeper).
3. **Frontend stays JavaScript/JSX.** Every page named below is a `.jsx` file with exactly the name given.
4. The landing page component, `landingPage.jsx`, **is written by another developer.** Only create the route, and
   a minimal placeholder file if the file doesn't exist yet. Say clearly that it is a placeholder. Do not design it.
5. No secrets in code. New settings go through `backend/app/core/config.py` and `.env.example`, and fail fast with
   variable *names* only, as the existing config does.
6. Never store plaintext passwords. Never log passwords, tokens or OAuth secrets.

## 3. Data model (new tables)

Keep the existing DB. Add:

1. **`users`**: `uid` (UUID PK), `username`, `email` (unique, indexed), `password_hash` (nullable, because
   Google-only users have none), plus the extras you need: `auth_provider` / `google_sub` (nullable, unique),
   `avatar_path` or `avatar_url` (nullable), `created_at`.
2. **`agents`**: `uid` (FK to users.uid, for lookup), `aid` (UUID PK, the agent id), plus the extras you need:
   `name`, `role_behavior` (text), `status` (free/busy, drives the dot colour), `created_at`, `updated_at`, and a
   nullable link to the existing `agent_profiles`/`agent_profile_versions` so the real voice agent can use the
   configured role. Decide the linkage after reading the profile code, and explain it.
3. **`managers`**: `uid` (FK, for lookup), `mid` (UUID PK, the manager id), plus what you need.
   Create one manager row per user (at signup or lazily on first visit).
4. Any extra table you need (for example payment records for the Payment step, or a user-to-workspace link).
   Create these at your discretion and justify each in one line.

**Link users to the existing data.** Calls are scoped by `workspace_id` today. Define how a `uid` maps to a
workspace so that each user sees only their own calls, transcripts and summaries, without altering the existing
tables. Prefer a new mapping table or a one-to-one user-to-workspace link. Every new endpoint must authorise by
the authenticated user and must never expose another user's agents or calls.

## 4. Authentication and authorization

- **Email + password:** register and login endpoints. Hash with argon2 or bcrypt, validate input (email format,
  password length), generic error messages, and rate-limit login (reuse `app/core/ratelimit.py`).
- **Google sign-in:** OAuth 2.0 / OIDC authorization-code flow. Verify the ID token server-side (signature,
  `aud`, `iss`, `exp`, `email_verified`). Create the user on first login and link by email or `google_sub`.
  This needs `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` and a redirect URI from the user. **Ask for them, and
  never fabricate credentials.** Document the setup in the README.
- **Access token:** a signed JWT (or an equivalent signed token) in an **httpOnly, SameSite, Secure-in-prod cookie**,
  with `sub=uid` and `exp`. Use a dedicated secret setting, and keep it separate from `WORKSPACE_COOKIE_SECRET`.
  Add CSRF protection for state-changing requests, and a `state`/nonce check on the OAuth flow.
- **Auth middleware / dependency** (backend `get_current_user`, plus a frontend route guard) must check:
  (a) the token is **present**, (b) it is **valid** (signature, not expired), (c) it **has not been tampered with**,
  and (d) the user still exists. Return 401 on any failure.
- **Authorization:** every `/…/{uid}` resource route must verify that the `uid` in the URL **equals the token's
  uid**; otherwise return 403. The same applies to `aid`: the agent must belong to that uid.
- **Session endpoint:** for example `GET /api/v1/auth/me` returns the current user, or 401. The frontend guard uses it.
- **Logout:** clears the cookie server-side.

## 5. Routing and redirect rules

| Situation | Behaviour |
|---|---|
| Anyone opens `/home` (`<deployment_link>/home`) | Renders `landingPage.jsx`. A dedicated middleware/guard runs: if the token is **present, valid and untampered** → redirect to `/dashboard/:uid`. If the user is new, or the token is missing, expired or invalid → redirect to `/checkin`. |
| `/checkin` | Sign-in / sign-up page with Email and Google options. |
| Successful authentication | Redirect to `/dashboard/:uid`. |
| Any protected page without a valid token | Redirect to `/checkin`. |
| Logout button | Clears the session, then redirects to `/checkin`. |

Decide, and state, how `/` behaves (suggest redirecting to `/home`). Because the frontend is a SPA, the
"middleware" is a backend token-check endpoint plus a frontend route guard / loader, so the check is not only
client-side trust: the backend remains the source of truth.

## 6. Pages and routes (frontend, all `.jsx`)

Shared rule: **`Dashboard.jsx`, `MyAgents.jsx`, `MyManager.jsx`, `ProfilePage.jsx` and `Settings.jsx` must all render
the same vertical `Navbar` component on the left.** This is a hard rule, so build one shared layout/component and
do not duplicate it.

**Vertical navbar:** `NavLink`s in this exact order:
1. My Dashboard → `/dashboard/:uid`
2. My Agents → `/agents/:uid`
3. My Manager → `/manager/:uid`
4. My Profile → `/profile/:uid`
5. Settings → `/settings/:uid`

### 6.1 `Dashboard.jsx` — `/dashboard/:uid`
- Left: the vertical navbar. Right: a `div` with `display:flex; flexDirection:'column'` holding two divs.
- **Upper div:** left half shows `Welcome back, <User_Name>!`; right half shows a **profile icon**. Clicking the
  icon navigates to `/profile/:uid` (`ProfilePage.jsx`).
- **Lower div:** empty for now.

### 6.2 `MyAgents.jsx` — `/agents/:uid`
- Left: the navbar. Right: a column flex with two divs.
- **Upper div:** the text `<User_Name>’s agents` and a **"Create new agent +"** button in the right half. The
  button goes to `/create_agent/:uid` (`AgentCreater.jsx`).
- **Lower div:** a box that renders the user's agents as **square boxes**. Each box is a column flex with two divs:
  - Upper: on the left a small circle (**green = free, red = under work/on a call**); on the right a **three-dot
    icon** that navigates to `/agents/:uid/update/:aid` (`AgentUpdater.jsx`).
  - Lower: the agent's **name, centred**.
- The busy/free state must come from real data (the `status` column or the live call state), not a hard-coded value.

### 6.3 `MyManager.jsx` — `/manager/:uid`
- Same design as the **existing chat page**. Reuse the current components and design (`ChatPage.jsx`, `ChatBox`,
  `Sphere`, `Sidebar`, `SummaryPanel`/`SummaryCard`, `CallControls`, `CallPage.jsx`, and the existing CSS).
  Do not rebuild them. **Make sure nothing is forgotten.** Go through the existing chat/call page and carry over
  every part of it:
  - a vertical **calls bar** on the left (this is the page's own sidebar of calls, in addition to the shared
    navbar; place them so both fit, and state your layout decision);
  - the **chat box with the moving sphere** and the **transcripts** of the user and the manager agent;
  - clicking a call in the bar **highlights** it and shows **that call's transcript** in the middle;
  - clicking a call also shows the **Call Summary component on the far right** (same third panel as now);
  - the live-call controls, elapsed time, reduced-motion handling, and loading/error states that the current UI has.
- **Difference:** the agent here is the **manager agent**, a voice agent with knowledge of **all the user's agents**
  (which are busy/on a call, which are free, and what each did today). Details of its capabilities will be provided
  later, so build the plumbing now: a manager profile/prompt, scoped per `uid`, that is fed the user's agents and
  their status, and structure it so more tools can be added later. Do not invent extra manager capabilities.
- Manager calls must be stored in the existing call/transcript/summary tables, and be distinguishable (for example
  via the manager link) without changing those tables' schema. State how you did it.

### 6.4 `ProfilePage.jsx` — `/profile/:uid`
- Left: the navbar. Right: user details: **profile picture, username, email, number of agents**, and a **Logout**
  button (→ `/checkin`).
- The user can **upload a profile picture**. Validate file type and size server-side, store it safely (a
  non-guessable filename, served from a controlled path), and show it on this page and in the Dashboard profile icon.

### 6.5 `Settings.jsx` — `/settings/:uid`
- Left: the navbar. Right: a **Light/Dark theme toggler** (only this, for now). Persist the choice (`localStorage`
  wrapped in try/catch, or per-user server-side), apply it app-wide with CSS variables, and ensure the existing
  styles in `frontend/src/styles/app.css` work in both themes.

### 6.6 `AgentCreater.jsx` — `/create_agent/:uid` (keep this spelling)
- A **box centred** in the UI with two fields: **"What would be the agent's name?"** and **"What would be the role
  and behaviour of the agent?"**. At the bottom are **"Cancel"** (back to `/agents/:uid`) and **"Create agent"**.
- **"Create agent"** navigates to `/create_agent/:uid/:aid` which renders `Payment.jsx`. The `aid` therefore must
  exist at that moment: create the agent row in a **pending/unpaid state** (not shown in the list, not usable) and
  activate it only after payment succeeds. Abandoned pending rows must not pollute the list.

### 6.7 `Payment.jsx` — `/create_agent/:uid/:aid`
- A centred box with a form that has **one input labelled "Enter amount"**.
- If the amount is **exactly 100**, the agent creation succeeds and the user is redirected to `/agents/:uid`,
  where the new agent shows with the older ones. Any other amount shows an error and creates nothing.
- This is a simulated payment. **Validate on the backend**, not only in the UI. Record the attempt. State clearly
  that no real payment gateway is integrated.

### 6.8 `AgentUpdater.jsx` — `/agents/:uid/update/:aid`
- A centred box with fields **"Update Agent name"** and **"Update role and behaviour of the agent"**, prefilled
  with the current values. At the bottom: **"Cancel"** and **"Save changes"**.
- "Save changes" persists the update, then redirects to `/agents/:uid`, where the changes are visible.
- If an agent is linked to a profile version, update it the way the existing profile versioning expects. Read
  `profile_service.py` first, and do not break versioning.

## 7. Backend API work

Add versioned routes under `/api/v1` for: auth (register, login, Google start/callback, me, logout), users (profile,
avatar upload), agents (list, create-pending, pay/activate, get, update), manager (get/ensure, token for the manager
voice session), and the user-scoped call listing. Every one is authenticated and scoped by the token's uid. Reuse
the existing patterns: `get_session`, error types in `app/core/errors.py`, `correlation_id`, the audit service
(`audit_service.py`) for sensitive events, and Pydantic schemas in `app/schemas/`. Add the new routers to
`app/main.py`.

Update the CORS/cookie settings for credentialed requests from `APP_ORIGIN`. Keep the Vite `/api` proxy working.

## 8. Frontend work

- Replace the router in `frontend/src/app/router.jsx` with the routes above, keeping the existing call/chat
  functionality reachable inside the new layout. Add the auth guard.
- Extend `api/api.js` (RTK Query) with the new endpoints, sending cookies (`credentials: 'include'`).
- Build the shared `Navbar` component and use it in the five pages listed in section 6.
- Handle loading, empty, error and 401/403 states everywhere. A 401 anywhere sends the user to `/checkin`.
- Keep the code style of the repo (Prettier: single quotes, no semicolons, width 110; check the existing files).

## 9. Quality bar

- Add backend tests (auth success and failure, tampered and expired token, uid mismatch → 403, agent ownership,
  payment 100 and non-100, migration applies cleanly on top of existing data) and frontend tests (guard redirects,
  navbar order and links, create/update/payment flows with mocked API).
- Run and report: backend tests, `ruff`/lint if configured, `npm run lint`, `npm test -- --run`, `npm run build`,
  and `alembic upgrade head` on the existing DB, checking that the existing rows (`calls`, `call_turns`,
  `call_summaries`) are intact.
- Then verify in the running app: sign up, log in, the Google flow (if credentials are available), dashboard, create
  and pay for an agent, update it, upload an avatar, the theme toggle, a manager call, and logout. Report what you
  could not verify.
- Update `README.md` and `.env.example` (new env vars, Google setup, run order). Don't commit or push unless asked.

## 10. Working method

1. Read the code named in section 1 and summarise the integration points in a few lines.
2. Propose the plan, the schema (migration 0002), the uid-to-workspace mapping, and any assumptions or questions
   (Google credentials, the manager design, how the `/` route behaves).
3. Implement in small steps in this order: migration and models → auth → user-scoped API → frontend shell, guard and
   navbar → pages → manager → tests → README.
4. At the end, give a report: what changed, where, what was verified, what is left, and the next command to run.

## 11. Source requirements checklist (all must be satisfied)

- [ ] `/home` landing route (`landingPage.jsx` placeholder only) with the token middleware (present / valid /
      untampered → `/dashboard/:uid`; otherwise → `/checkin`)
- [ ] `/checkin` with Google and Email authentication and authorization, as in real-world products
- [ ] Successful auth → `/dashboard/:uid` rendering `Dashboard.jsx`
- [ ] Dashboard: left navbar; right column with the upper div (`Welcome back, <User_Name>!` + profile icon →
      `/profile/:uid`) and an empty lower div
- [ ] Navbar order: My Dashboard, My Agents, My Manager, My Profile, Settings, with the routes in section 6;
      the same navbar on all five pages
- [ ] `MyAgents.jsx` at `/agents/:uid`: `<User_Name>’s agents`, "Create new agent +" → `/create_agent/:uid`; square
      agent boxes (status circle green/red, three-dot → `/agents/:uid/update/:aid`, centred name)
- [ ] `MyManager.jsx` at `/manager/:uid`: the same design as the current chat page (calls bar, highlight on
      click, transcript + moving sphere, Call Summary on the far right), with nothing forgotten; the manager is a
      voice agent aware of all the user's agents (busy/free, what each did today; more to come)
- [ ] `ProfilePage.jsx` at `/profile/:uid`: picture (uploadable), username, email, number of agents, Logout → `/checkin`
- [ ] `Settings.jsx` at `/settings/:uid`: Light/Dark toggle
- [ ] `AgentCreater.jsx`: centred box, two fields, Cancel / Create agent → `/create_agent/:uid/:aid`
- [ ] `Payment.jsx`: one field "Enter amount"; 100 → agent created, redirect to `/agents/:uid` with the new agent shown
- [ ] `AgentUpdater.jsx`: centred box, "Update Agent name", "Update role and behaviour of the agent", Cancel /
      Save changes → `/agents/:uid` showing the changes
- [ ] Tables `users(uid, username, email, password hashed)`, `agents(uid, aid)`, `managers(uid, mid)` + extras at
      your discretion; the existing call/transcript/summary schema is untouched; the same database
