# QuickDesk

## What this is

QuickDesk is an internal helpdesk SPA: employees submit tickets, FastAPI classifies them with Groq (keyword fallback if the key is missing), agents override category/priority, pull a RAG-grounded draft from six seeded Markdown articles, resolve the ticket, and watch open/resolved/median/override metrics. Passwords are bcrypt-hashed; access is JWT-based with role checks on the backend. React + Vite is the UI; PostgreSQL is the store; LangChain + Chroma (MiniLM embeddings) plus a lexical fallback power retrieval; live queue updates use SSE with one Uvicorn worker.

## How to run locally

Documented path: **Postgres via Docker**, then **FastAPI and Vite on the host**. Do not use `docker compose --profile full` for the graded run â€” that profile is optional packaging only.

### Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Python 3.11+ (3.12 is fine)
- Node.js 18+ and npm
- A free-tier [Groq Cloud](https://console.groq.com/) API key for AI reply drafts (and preferred classification)

### 1. Clone and create `.env`

```powershell
git clone <your-repo-url> QuickDesk
Set-Location QuickDesk
Copy-Item .env.example .env
notepad .env
```

Set at least:

```env
DATABASE_URL=postgresql+psycopg://quickdesk:quickdesk@localhost:5432/quickdesk
JWT_SECRET_KEY=quickdesk
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
QUICKDESK_ENV=dev
EMAIL_BACKEND=console
GROQ_API_KEY=
GROQ_MODEL=qwen/qwen3.8-27b
```

Paste your Groq key after `GROQ_API_KEY=` (never commit `.env`). `GROQ_MODEL` defaults to `qwen/qwen3.8-27b` on the Groq free tier â€” the same default as `backend/app/config.py` and `.env.example`.

`JWT_SECRET_KEY=quickdesk` is fine for a private local demo. For anything shared, use `openssl rand -hex 32` or Python `secrets.token_hex(32)`. If `JWT_SECRET_KEY` is empty and `QUICKDESK_ENV=dev`, the API generates an ephemeral secret at startup (restarts invalidate tokens).

### 2. Start PostgreSQL

```powershell
docker compose up -d
```

This starts only the `db` service (`postgres:16`, user/db `quickdesk`, port `5432`). Stop any other Postgres already bound to `5432` first.

### 3. Backend (migrate, seed, one worker)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Set-Location backend
python migrate.py
python seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Keep this terminal open. Health check: `http://127.0.0.1:8000/api/health`.

**On first successful startup**, `rebuild_index()` in `backend/app/main.py` loads seeded KB articles from Postgres, splits them, and writes a local Chroma collection under `backend/chroma_db/` (gitignored). It downloads Hugging Face `sentence-transformers/all-MiniLM-L6-v2` once into your HF cache (~90MB) for **embeddings only**. Chat classification and RAG drafts call **Groq** with `GROQ_API_KEY`. If embeddings/Chroma fail, retrieval falls back to lexical search over the same articles. Draft generation **requires** Groq and returns a clear error if the key is missing (no invented policy text). After reseeding an empty DB, restart Uvicorn so the index rebuilds.

Use **`--workers 1`**: the SSE hub in `backend/app/realtime.py` is process-local.

### 4. Frontend

Second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Seeded accounts

| Role     | Email                    | Password         |
| -------- | ------------------------ | ---------------- |
| Agent    | `agent@quickdesk.dev`    | `Agent#Pass1`    |
| Employee | `employee@quickdesk.dev` | `Employee#Pass1` |

`EMAIL_BACKEND=console` logs a mock resolution email to the backend console; it does not send real mail.

### Stop

`Ctrl+C` in the Uvicorn terminal, then:

```powershell
docker compose down
```

Add `-v` only if you also want to wipe the Postgres volume.

## Architecture

```text
                    +---------------------------+
 Employee / Agent   |  React + Vite :5173       |
 browsers           |  REST + localStorage JWT  |
                    |  EventSource (SSE)        |
                    +-------------+-------------+
                                  |
                     REST Bearer / SSE ?token=
                                  v
                    +---------------------------+
                    |  FastAPI (Uvicorn :8000)  |
                    |  JWT + bcrypt + require_role|
                    |  in-process SSE hub       |
                    +--+----------+----------+--+
                       |          |          |
                       v          v          v
                 PostgreSQL   Chroma +     Groq chat
                 :5432        MiniLM       api.groq.com
                 tickets,     (local       classify +
                 users, KB    chroma_db)   RAG drafts
                              + lexical
                              fallback
```

**RAG path (agent â€œGenerate AI draftâ€):** ticket title/description â†’ hybrid retrieve (dense Chroma + IDF lexical, RRF, top 3 chunks) â†’ validate chunk text against Postgres article â†’ expand to full article text for the prompt â†’ Groq draft â†’ reject ungrounded URLs / bad no-match replies â†’ save `ai_draft` + citations.

Resolution commits first, then console notify + user-scoped SSE. Notify failure cannot roll back the reply. SSE events are invalidation signals; REST is the source of truth.

## Stack (as implemented)

| Layer | Choice |
| ----- | ------ |
| Frontend | React 18 + Vite 6 + React Router (not Next.js) |
| Backend | Python FastAPI + Uvicorn |
| Database | PostgreSQL 16 (Docker) |
| Auth | JWT (HS256, 60 min) + bcrypt password hashes |
| LLM | Groq free tier, model `qwen/qwen3.8-27b` (override via `GROQ_MODEL`) |
| RAG | LangChain text splitter + HuggingFace MiniLM embeddings + Chroma; lexical fallback |
| Realtime | Server-Sent Events (`GET /api/events`) |

## API endpoints

| Method | Path | Purpose | Auth |
| ------ | ---- | ------- | ---- |
| GET | `/api/health` | Liveness | Public |
| POST | `/api/auth/register` | Register an employee | Public |
| POST | `/api/auth/login` | Issue JWT + user summary | Public |
| GET | `/api/auth/me` | Current user | Bearer JWT |
| POST | `/api/auth/change-password` | Change own password | Bearer JWT |
| GET | `/api/agents/summary` | Tiny agent-only probe | Agent |
| GET | `/api/events?token=...` | SSE invalidation stream | JWT query param |
| GET | `/api/metrics` | Status counts, categories, median resolution, override rate | Agent |
| GET | `/api/kb/articles/{id}` | Full KB article for a citation | Agent |
| POST | `/api/tickets` | Create ticket + classify | Employee or agent |
| GET | `/api/tickets/mine` | List own tickets | Employee or agent |
| GET | `/api/tickets` | Agent queue (filter/paginate) | Agent |
| GET | `/api/tickets/{id}` | Ticket detail + override history | Agent, or owning employee |
| PATCH | `/api/tickets/{id}/classification` | Override final category/priority | Agent |
| POST | `/api/tickets/{id}/ai-draft` | Retrieve + Groq draft + citations | Agent |
| POST | `/api/tickets/{id}/reply` | Final reply, resolve, notify, SSE | Agent |

## Decisions and Tradeoffs

### a) Why React + Vite, not Next.js?

QuickDesk is a signed-in internal tool with two role workspaces (employee vs agent), not a public marketing site. There is no SEO requirement and no need for server-rendered pages. FastAPI already owns auth, classification, RAG, and resolution. Adding Next.js would mean a second Node server and deployment path for the same SPA routes (login, my tickets, agent queue, ticket detail, metrics). Vite + React Router keeps the frontend as a thin authenticated client against `/api/*`.

### b) How is the RAG pipeline structured?

Seeded Markdown under `backend/kb/` is loaded into Postgres by `seed.py` (six articles). On startup, `rebuild_index()` splits article content with LangChain `RecursiveCharacterTextSplitter` at **chunk_size=500**, **chunk_overlap=50**. Embeddings use local Hugging Face **`sentence-transformers/all-MiniLM-L6-v2`** into a persistent Chroma collection `quickdesk_kb` under `backend/chroma_db/` (cosine space).

Retrieval for a ticket (`get_relevant_chunks` in `rag.py`):

1. Build query = title + description.
2. **Dense:** Chroma `similarity_search_with_relevance_scores`, keep scores **â‰¥ 0.2**, up to 8.
3. **Lexical:** IDF-weighted term scores; require **â‰¥ 2** overlapping content terms (stop words / generic words stripped); top 8.
4. **Fuse** with reciprocal-rank fusion (`1/(60+rank)`), keep at most **3** chunks.
5. `grounded_context` reloads full article bodies from Postgres and drops citations whose chunk text is not a substring of the stored article.
6. `generate_reply` in `llm.py` prompts Groq with those excerpts only: no invented URLs/policies; if no excerpts, the model must say there is no documented knowledge yet and that we will look into it and get back â€” otherwise the draft is rejected and nothing is saved.

### c) Invalid LLM category / priority?

Allowlists in `llm.py`: categories `{IT, HR, Finance, Admin, Other}`, priorities `{Low, Medium, High}`. Groq is asked for JSON with only those labels. `_normalize_classification` returns `None` if either label is off-list; classify then falls back to keyword scoring. Keyword miss (no term hits) or total classify failure stores **Other / Medium** and `ai_classified=False`. Agents still own `final_category` / `final_priority` via the override endpoint.

### d) Where is the JWT stored on the client, and why?

In **`localStorage`** under key `quickdesk_token` (`AuthContext.jsx` + axios interceptor in `api/client.js`). That avoids CSRF complexity for a Bearer SPA and keeps `EventSource` able to pass the same token as `?token=` (browsers cannot set `Authorization` on EventSource). Tradeoff: any XSS can read the token. Acceptable for this assessment; production would want HTTPS, shorter TTLs, refresh rotation, and a tighter cookie strategy.

### e) Backend RBAC â€” what stops an employee guessing an agent URL?

UI route guards (`Protected` in `App.jsx`) only hide pages. Real enforcement is FastAPI: `get_current_user` validates the JWT; `require_role("agent")` protects agent list, metrics, KB article, classification override, AI draft, and reply. Ticket `GET /{id}` allows an agent or the **owning** employee (`employee_id` check â†’ 403 otherwise). Guessing `/api/tickets` or `/api/metrics` with an employee token still returns **403**. Hiding a nav link is not the security boundary.

### f) Why SSE instead of Socket.io / WebSockets? Disconnect failure mode?

Updates are one-way server â†’ browser invalidations (`ticket_created` to agents, `ticket_resolved` to the employee). `EventSource` reconnects with backoff in `useTicketEvents.js`; on open/error the UI refetches REST. Socket.io would add another realtime stack and bidirectional protocol we do not need. A raw WebSocket would need custom heartbeat/reconnect for the same signal.

**Failure mode:** the hub is an in-process `asyncio.Queue` set (`realtime.py`). With multiple Uvicorn workers, events published in worker A are invisible to connections on worker B â€” hence **`--workers 1`**. If the stream drops mid-session, the client may miss an event until reconnect + REST refetch. A full queue (max 50) drops that connection. Redis pub/sub (or similar) would be required before scaling workers.

### g) Worst failure mode today, and what I would do?

**Worst:** SSE disconnect / multi-worker miss leaves an employee staring at **Open** after an agent resolved the ticket, until they refresh or the EventSource recovers and refetches. Closely related: a missing or broken `GROQ_API_KEY` blocks AI drafts entirely (clear 503, no saved draft) while ticket create still works via keyword classify.

**Address:** move the hub to Redis (or Postgres NOTIFY) so workers share events; add a short-lived â€œlast event idâ€ or periodic poll on the employee My Tickets page; for Groq, retries/backoff and a dashboard health flag when the key/model fails.

### h) Where AI tools helped, and where they hurt?

AI scaffolding got FastAPI routers, React pages, and the LangChain/Chroma shape standing quickly, which mattered under a short deadline. It also left integration landmines that only showed up when walking the real agent queue: optimistic SSE inserts still reason about **`ai_category` / `ai_priority`** while the list API filters on **`final_category` / `final_priority`**, so a filtered queue can disagree with a live insert; employee ticket deep-links and ownership edge cases needed another human pass after the generated UI looked â€œdone.â€ I treat generated code as a first draft and verify every role path against the live API before calling a feature finished.

## What I would do with more time

- Replace hand-rolled `migrate.py` with Alembic.
- Move SSE fan-out to Redis pub/sub (or equivalent) and allow multiple workers.
- Fix the agent-queue live-insert filter to use final classification fields consistently with `GET /api/tickets`.
- Add real SMTP behind `EMAIL_BACKEND`, with delivery failure surfacing in the UI.
- Add `pg_trgm` (or similar) for title search instead of bare `ILIKE`.
- Refresh-token rotation and stop putting long-lived JWTs only in `localStorage`.
- Automated API + a couple of Playwright role flows; right now verification is the manual smoke path.
- Record and link the 3â€“5 minute demo video (recording outline lives at `docs/demo-recording.html`).

## Known issues / limitations

- **No demo video in the repo yet** â€” use `docs/demo-recording.html` as the shot list when recording.
- Documented Compose path is **Postgres only**; `backend` / `frontend` services sit behind Compose profile `full` and are optional, not the graded workflow.
- SSE hub is process-local â†’ must run Uvicorn with one worker.
- SSE auth uses a query-string JWT because EventSource cannot send Bearer headers.
- Chroma index rebuilds on process start; there is no live â€œreindex KBâ€ API.
- Title search is `ILIKE`, not indexed full-text.
- Agent dashboard live `ticket_created` handling still compares filters to **`ai_*`** fields while REST listing filters **`final_*`** â€” can disagree after overrides or with filters on.
- JWTs in `localStorage`, no refresh tokens; default expiry 60 minutes.
- Console notifier only; no outbound email.
- Groq outage or empty `GROQ_API_KEY` â†’ draft endpoint errors; classification can still keyword-fallback.
- Stretch goals are capped at two (below). Full Compose is packaging, not a stretch claim.

### Stretch goals (2/2)

1. **Console resolution email** â€” `EMAIL_BACKEND=console` builds and logs a plain-text mock mail after a successful resolve commit.
2. **AI confidence** â€” `tickets.ai_confidence` (0â€“100, nullable) from Groq or keyword match strength, shown next to suggested category/priority.

## Pre-submission smoke checklist

1. Employee login â†’ New ticket (e.g. VPN / production) â†’ appears Open under My tickets.
2. Agent login â†’ queue shows the ticket without a full page reload (SSE).
3. Agent opens ticket â†’ Generate AI draft â†’ draft text + citation chip(s).
4. Edit draft â†’ Send reply â†’ Resolved; employee My tickets flips to Resolved via SSE.
5. Override category on another ticket â†’ â€œchangedâ€ / override history; Metrics override rate moves.
6. Backend console shows a `MOCK EMAIL` block on resolve.
7. Logout / login again; employee cannot call agent-only APIs successfully.
