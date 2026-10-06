# QuickDesk

QuickDesk is an internal helpdesk: employees submit tickets, FastAPI classifies them with Groq, agents override category/priority, pull a RAG-grounded draft from six seeded Markdown articles, resolve the ticket, and watch open/resolved/median/override metrics. Passwords are bcrypt-hashed; access is JWT-based with role checks on the backend. React + Vite is the UI; PostgreSQL is the store; LangChain + Chroma (MiniLM embeddings) power retrieval; live queue updates use SSE with one Uvicorn worker.

## Steps to run locally

Documented path: **Postgres via Docker**, then **FastAPI and Vite on the host**. Do not use `docker compose --profile full` for the graded run — that profile is optional packaging only.

### Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Python 3.11+ (3.12 is fine)
- Node.js 18+ and npm
- A free-tier [Groq Cloud](https://console.groq.com/) API key for AI reply drafts (and preferred classification)

### 1. Clone and create `.env`

```powershell
git clone https://github.com/priyansupattanaik/QuickDesk
Set-Location QuickDesk
Copy-Item .env.example .env
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

**On first successful startup**, `rebuild_index()` in `backend/app/main.py` loads seeded KB articles from Postgres, splits them, and writes a local Chroma collection under `backend/chroma_db/` (gitignored). It downloads Hugging Face `sentence-transformers/all-MiniLM-L6-v2` once into your HF cache (~90MB) for **embeddings only**. Chat classification and RAG drafts call **Groq**. If embeddings or Chroma fail, retrieval returns an error and no draft is saved. Draft generation and classification **require** Groq and return a clear error if the key is missing (no invented category or policy text). After reseeding an empty DB, restart Uvicorn so the index rebuilds.

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
```

**RAG path (agent “Generate AI draft”):** ticket title/description → hybrid retrieve (dense Chroma + IDF lexical, RRF, top 3 chunks) → validate chunk text against Postgres article → expand to full article text for the prompt → Groq draft → reject ungrounded URLs / bad no-match replies → save `ai_draft` + citations.

## Stack (as implemented)

| Layer    | Choice                                                           |
| -------- | ---------------------------------------------------------------- |
| Frontend | React 18 + Vite 6 + React Router (not Next.js)                   |
| Backend  | Python FastAPI + Uvicorn                                         |
| Database | PostgreSQL 16 (Docker)                                           |
| Auth     | JWT (HS256, 60 min) + bcrypt password hashes                     |
| LLM      | Groq free tier, model `qwen/qwen3.8-27b`                         |
| RAG      | LangChain text splitter + HuggingFace MiniLM embeddings + Chroma |
| Realtime | Server-Sent Events (`GET /api/events`)                           |

## API endpoints

| Method | Path                               | Purpose                                                     | Auth                      |
| ------ | ---------------------------------- | ----------------------------------------------------------- | ------------------------- |
| GET    | `/api/health`                      | Liveness                                                    | Public                    |
| POST   | `/api/auth/register`               | Register an employee                                        | Public                    |
| POST   | `/api/auth/login`                  | Issue JWT + user summary                                    | Public                    |
| GET    | `/api/auth/me`                     | Current user                                                | Bearer JWT                |
| POST   | `/api/auth/change-password`        | Change own password                                         | Bearer JWT                |
| GET    | `/api/agents/summary`              | Tiny agent-only probe                                       | Agent                     |
| GET    | `/api/events?token=...`            | SSE invalidation stream                                     | JWT query param           |
| GET    | `/api/metrics`                     | Status counts, categories, median resolution, override rate | Agent                     |
| GET    | `/api/kb/articles/{id}`            | Full KB article for a citation                              | Agent                     |
| POST   | `/api/tickets`                     | Create ticket + classify                                    | Employee or agent         |
| GET    | `/api/tickets/mine`                | List own tickets                                            | Employee or agent         |
| GET    | `/api/tickets`                     | Agent queue (filter/paginate)                               | Agent                     |
| GET    | `/api/tickets/{id}`                | Ticket detail + override history                            | Agent, or owning employee |
| PATCH  | `/api/tickets/{id}/classification` | Override final category/priority                            | Agent                     |
| POST   | `/api/tickets/{id}/ai-draft`       | Retrieve + Groq draft + citations                           | Agent                     |
| POST   | `/api/tickets/{id}/reply`          | Final reply, resolve, notify, SSE                           | Agent                     |

## Decisions and Tradeoffs

### a) Why React + Vite, not Next.js?

QuickDesk is a signed-in internal tool with two role workspaces (employee vs agent), not a public marketing site. There is no SEO requirement and no need for server-rendered pages. FastAPI is already handling auth, classification, RAG, and resolution. Adding Next.js would mean a second Node server and deployment path for the same SPA routes (login, my tickets, agent queue, ticket detail, metrics). Vite + React Router keeps the frontend as a thin authenticated client against `/api/*`.

### b) How is the RAG pipeline structured?

Seeded Markdown under `backend/kb/` is loaded into Postgres by `seed.py` (six articles). On startup, `rebuild_index()` splits article content with LangChain `RecursiveCharacterTextSplitter` at **chunk_size=500**, **chunk_overlap=50**. Embeddings use local Hugging Face **`sentence-transformers/all-MiniLM-L6-v2`** into a persistent Chroma collection `quickdesk_kb` under `backend/chroma_db/`.

Retrieval for a ticket (`get_relevant_chunks` in `rag.py`):

1. Build query = title + description.
2. **Dense:** Chroma `similarity_search_with_relevance_scores`, keep scores **≥ 0.2**, up to 8.
3. **Lexical:** IDF-weighted term scores; require **≥ 2** overlapping content terms (stop words / generic words stripped); top 8.
4. Keep an embedding hit only when it also shares those content terms. There is no lexical-only result. At most **3** chunks are returned.
5. `grounded_context` reloads full article bodies from Postgres and drops citations whose chunk text is not a substring of the stored article.
6. `generate_reply` in `llm.py` prompts Groq with those excerpts only: no invented URLs/policies; if no excerpts, the model must say there is no documented knowledge yet and that we will look into it and get back — otherwise the draft is rejected and nothing is saved.

### c) Invalid LLM category / priority?

Allowlists in `llm.py`: categories `{IT, HR, Finance, Admin, Other}`, priorities `{Low, Medium, High}`. Groq is asked for JSON with only those labels. If either label is off-list, or Groq fails, the ticket is not created. Agents still own `final_category` / `final_priority` via the override endpoint.

### d) Where is the JWT stored on the client, and why?

In **`localStorage`** under key `quickdesk_token` (`AuthContext.jsx` + axios interceptor in `api/client.js`). That avoids CSRF complexity for a Bearer SPA and keeps `EventSource` able to pass the same token as `?token=` (browsers cannot set `Authorization` on EventSource). Tradeoff: any XSS can read the token. For a production level application it would want HTTPS, shorter TTLs, refresh rotation, and a tighter cookie strategy.

### e) Backend RBAC — what stops an employee guessing an agent URL?

UI route guards (`Protected` in `App.jsx`) only hide pages. Real enforcement is FastAPI: `get_current_user` validates the JWT; `require_role("agent")` protects agent list, metrics, KB article, classification override, AI draft, and reply. Ticket `GET /{id}` allows an agent or the **owning** employee (`employee_id` check → 403 otherwise). Guessing `/api/tickets` or `/api/metrics` with an employee token still returns **403**. Hiding a nav link is not the security boundary.

### f) Why SSE instead of Socket.io / WebSockets? Disconnect failure mode?

Updates are one-way server → browser invalidations (`ticket_created` to agents, `ticket_resolved` to the employee). `EventSource` reconnects with backoff in `useTicketEvents.js`; on open/error the UI refetches REST. Socket.io would add another realtime stack and bidirectional protocol we do not need. A raw WebSocket would need custom heartbeat/reconnect for the same signal.

**Failure mode:** the hub is an in-process `asyncio.Queue` set (`realtime.py`). With multiple Uvicorn workers, events published in worker A are invisible to connections on worker B — hence **`--workers 1`**. If the stream drops mid-session, the client may miss an event until reconnect + REST refetch. A full queue (max 50) drops that connection. Redis pub/sub (or similar) would be required before scaling workers.

### g) Where AI tools helped, and where they hurt?

The design decisions were mine. I designed the frontend, the RAG pipeline, and the overall architecture, and I chose the stack and decided how and why each piece is used. Most of the implementation and coding was done with AI tools: Codex, Groq, and Antigravity. They wrote most of the code from my design, helped me debug, fixed the flow of the application, and handled minor frontend changes. Where they hurt was integration: generated code often looked finished before it actually worked end to end, so I still had to check each role path and flow myself before its done.

## What I would do with more time

- Replace hand-rolled `migrate.py` with Alembic.
- Move SSE fan-out to Redis pub/sub (or equivalent) and allow multiple workers.
- Fix the agent-queue live-insert filter to use final classification fields consistently with `GET /api/tickets`.
- Add real SMTP behind `EMAIL_BACKEND`, with delivery failure surfacing in the UI.
- Add `pg_trgm` (or similar) for title search instead of bare `ILIKE`.
- Refresh-token rotation and stop putting long-lived JWTs only in `localStorage`.

## Known issues / limitations

- SSE hub is process-local → must run Uvicorn with one worker.
- SSE auth uses a query-string JWT because EventSource cannot send Bearer headers.
- Chroma index rebuilds on process start; there is no live “reindex KB” API.
- Title search is `ILIKE`, not indexed full-text.
- Agent dashboard live `ticket_created` handling still compares filters to **`ai_*`** fields while REST listing filters **`final_*`** — can disagree after overrides or with filters on.
- JWTs in `localStorage`, no refresh tokens; default expiry 60 minutes.
- Console notifier only; no outbound email.
- Groq outage or empty `GROQ_API_KEY` stops ticket creation and draft generation. Nothing is classified or drafted by a local substitute.
- Stretch goals are capped at two (below). Full Compose is packaging, not a stretch claim.

### Stretch goals (2/2)

1. **Console resolution email** — `EMAIL_BACKEND=console` builds and logs a plain-text mock mail after a successful resolve commit.
2. **AI confidence** — `tickets.ai_confidence` (0–100, nullable) from Groq, shown next to suggested category and priority.
