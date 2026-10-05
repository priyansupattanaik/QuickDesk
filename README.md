# QuickDesk

## What this is

QuickDesk is an internal helpdesk where employees submit tickets and agents classify, search, draft, resolve, and measure support work. FastAPI is the authority for roles, ownership, classification values, resolution state, and audit history; React provides the two role-specific workspaces.

## How to run locally

Run these commands from the repository root in this order.

```powershell
docker compose up -d
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
if (Get-Command openssl -ErrorAction SilentlyContinue) { openssl rand -hex 32 } else { python -c "import secrets; print(secrets.token_hex(32))" }
```

Put the printed value in `JWT_SECRET_KEY` in `.env`. OpenSSL is the preferred generator. The Python fallback is in the same command because a normal Windows PATH often includes Git but not `openssl.exe`. Leave `NVIDIA_API_KEY` empty to use classification and draft fallbacks (template drafts with a `degraded` flag), or add a key from [build.nvidia.com](https://build.nvidia.com) for live NVIDIA NIM replies. The assignment brief listed several LLM vendors; this repo uses **NVIDIA NIM** via the OpenAI-compatible client. No key belongs in Git.

**Knowledge base index and embeddings (first run):** On startup, `backend/app/main.py` calls `rebuild_index()`, which reads seeded KB articles from Postgres and writes a local Chroma collection under `backend/chroma_db/` (gitignored). The first successful run downloads `sentence-transformers/all-MiniLM-L6-v2` into your Hugging Face cache (~90MB). If the model or index is missing, the service uses a grounded lexical fallback over the same Postgres articles, so drafts still succeed with citations. Re-run `python seed.py` then restart Uvicorn to rebuild after an empty database.

```powershell
Set-Location backend
python migrate.py
python seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Use one Uvicorn worker because the Phase 3 SSE hub is process-local. In another terminal, from the repository root:

```powershell
Set-Location frontend
npm install
npm run build
npm run dev
```

Open `http://localhost:5173`. The seeded credentials are:

| Role | Email | Password |
| --- | --- | --- |
| Agent | `agent@quickdesk.dev` | `Agent#Pass1` |
| Employee | `employee@quickdesk.dev` | `Employee#Pass1` |

`python migrate.py` creates the schema on an empty database and adds the final-classification columns when `tickets` already exists. It is safe to run repeatedly, and it must run before `seed.py`. The console notifier is selected by default with `EMAIL_BACKEND=console`; a real SMTP implementation is the documented future swap.

The command above starts only Postgres. The API and Vite app still run on the host so the local MiniLM cache and one-worker SSE hub stay on this machine. To run the whole stack in containers instead:

```powershell
docker compose --profile full up --build
```

That profile migrates, seeds the demo users and knowledge-base articles, and serves the UI at `http://localhost` with the API on port 8000. Do not run host Uvicorn on port 8000 at the same time. The first container start can log a knowledge-base miss because the embedding model is loaded with `local_files_only`; ticket creation and console email still work, and drafts fall back to the template.

## Architecture

```text
Employee browser ── REST + localStorage JWT ──┐
                                              v
Agent browser ◀── SSE invalidation ─── FastAPI :8000
       │                                      │
       │                                      ├── SQLAlchemy ── Postgres :5432
       │                                      ├── ChromaDB + local MiniLM
       │                                      └── console mock notifier
       │
React/Vite :5173 ◀── REST refetch on SSE open/events
```

Ticket resolution commits first, then emits a user-scoped SSE invalidation and attempts the console mock email. Notification failure is logged and cannot roll back the already committed reply. SSE is an in-process hub; clients refetch REST data so events are signals, not the source of truth.

## API endpoints

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/health` | Health check | Public |
| POST | `/api/auth/register` | Register an employee | Public |
| POST | `/api/auth/login` | Issue a JWT and return the user | Public |
| GET | `/api/auth/me` | Return the signed-in user | Authenticated |
| GET | `/api/agents/summary` | Return agent summary data | Agent |
| GET | `/api/events?token=...` | Stream ticket invalidation events | Authenticated query-param JWT |
| GET | `/api/metrics` | Return status, category, median, and override metrics | Agent |
| GET | `/api/kb/articles/{id}` | Open the authenticated source article behind a citation | Agent |
| POST | `/api/tickets` | Create and classify a ticket | Employee or agent |
| GET | `/api/tickets/mine` | List the signed-in employee's tickets | Employee or agent |
| GET | `/api/tickets` | Filter and paginate the agent queue | Agent |
| GET | `/api/tickets/{id}` | Return ticket detail and audit history | Agent or owning employee |
| PATCH | `/api/tickets/{id}/classification` | Override final category and/or priority | Agent |
| POST | `/api/tickets/{id}/ai-draft` | Retrieve citations and save an AI draft | Agent |
| POST | `/api/tickets/{id}/reply` | Save final reply and resolve the ticket | Agent |

## Decisions and tradeoffs

- I use ChromaDB in local persistent mode instead of FAISS because this six-article corpus needs a directory-backed collection and document metadata without another service. The retrieval behavior remains local and the index is rebuilt on startup.
- I use `sentence-transformers/all-MiniLM-L6-v2` locally. LangChain's `RecursiveCharacterTextSplitter` creates 500-character chunks with 50-character overlap. Retrieval fuses dense Chroma matches with an IDF-weighted lexical rank, then applies deterministic reciprocal-rank fusion and returns at most three evidence chunks.
- Each citation is validated against the current PostgreSQL article before it is persisted. The agent can click a citation and open the authenticated `/kb/{id}` source page, which displays the exact stored article content. A generated answer that contains unsupported vocabulary fails the conservative grounding check and is replaced by a grounded fallback draft.
- I use NVIDIA NIM through the OpenAI-compatible client with the configured `meta/llama-3.2-11b-vision-instruct` model. Provider, parse, timeout, and validation failures fall back to `Other`/`Medium` and never block ticket creation.
- I keep `ai_category` and `ai_priority` as the original model output and store agent decisions in `final_category` and `final_priority`. `override_logs` records each changed field, old value, new value, agent, and timestamp.
- I use the `bcrypt` package directly. passlib is unmaintained, and its version check breaks against bcrypt 4.x.
- I use PyJWT instead of python-jose. python-jose has the weaker maintenance path and the CVE history I did not want in this service. Access tokens expire after 60 minutes.
- I store the JWT in localStorage. For this internal tool I accept the XSS exposure in exchange for avoiding CSRF. Refresh tokens and rotation remain future work. The backend still verifies every role and ownership decision.
- Public registration can only create an employee. Agent accounts come from seed or operations, never from self-serve signup.
- I use `require_role()` as a dependency factory so every protected route shares one authorization choke point.
- I use Server-Sent Events for live ticket updates, not Socket.io and not a native WebSocket. The dashboard and My Tickets only need the server to push an invalidation; the browser never sends ticket data upstream on that channel. SSE stays on the existing HTTP API, passes through the Vite dev server and the nginx `/api/` proxy (`proxy_buffering off`), and `EventSource` reconnects on its own. Socket.io would add a second realtime server and a client library for a channel this app does not use in both directions. A raw WebSocket would need its own upgrade route, heartbeat, and reconnect code to deliver the same signal. `EventSource` cannot set an `Authorization` header, so `GET /api/events` takes the JWT as a query parameter. The hub is in-process, so Uvicorn runs with `--workers 1`; opening the stream refetches REST, which recovers any event missed during a reconnect. Redis pub/sub would be required before adding workers.
- I use SQL aggregates and PostgreSQL `percentile_cont(0.5)` for median resolution time. Override rate uses null-safe `IS DISTINCT FROM`, so fallback/null values do not create false overrides.
- I use a hand-written `migrate.py` for the additive final-classification columns and `override_logs` table. The change is small enough that Alembic can wait.
- I use `EMAIL_BACKEND=console` for resolution mail. The notifier builds a plain-text email and logs it after commit; SMTP is a documented swap, not an unimplemented claim.
- I store the model's `confidence` integer (0–100) on `tickets.ai_confidence` and show it beside the suggested category and priority. A missing or invalid score stays null. The no-key fallback does not invent a score.
- I ship a Compose `full` profile for backend, frontend, and Postgres. Plain `docker compose up -d` still starts only Postgres so the host-run instructions keep working.

## Assignment questions a–h

- **a. React vs Next:** I chose React with Vite because this is a role-based internal SPA: the browser needs fast authenticated transitions, not SEO, server rendering, or a second server layer. Next would be reasonable if SSR, public pages, or server-side route handling became requirements.
- **b. RAG structure:** Seeded Markdown articles are stored in Postgres, split with LangChain's `RecursiveCharacterTextSplitter` at 500 characters with 50 characters of overlap, embedded with `all-MiniLM-L6-v2`, and retrieved from Chroma with `k=3` and a 0.2 threshold. If embeddings are unavailable, lexical overlap over the same Postgres articles is the grounded fallback. The prompt contains only retrieved excerpts and requires an explicit no-match response.
- **c. Invalid LLM category:** The classifier validates categories and priorities against the backend allowlists. Invalid JSON or values get one JSON-only retry; if that still fails, the ticket uses `Other`/`Medium` and records that the result was not AI-classified.
- **d. JWT storage:** The frontend stores the access token in `localStorage` for this assessment because it avoids CSRF complexity and keeps the API client simple. That accepts the XSS tradeoff; a production hardening pass would use HTTPS, short-lived access tokens, refresh-token rotation, and a carefully scoped cookie strategy.
- **e. Backend RBAC:** `get_current_user` authenticates the token, `require_role` protects agent-only routers, and ticket ownership is checked in the ticket service. Guessing an agent URL therefore still reaches the backend guard and returns `403`; hiding a button is not the security boundary.
- **f. Realtime choice:** I chose SSE because queue updates are one-way server-to-browser invalidations and `EventSource` reconnects automatically. On disconnect or reconnect the client refetches the REST list, so a missed event is recoverable. The in-process hub is intentionally one-worker; Redis or a broker would be the next step for multi-worker deployment.
- **g. Worst failure mode:** Provider or embedding failure is the most important degraded path. Ticket creation and grounded lexical drafts still work, while live provider failures fall back without inventing citations. Production mitigation would add a cached model, provider timeouts/retries, circuit breaking, and metrics; authentication and ownership remain backend-controlled.
- **h. AI help and harm:** AI accelerated the initial routes, UI, tests, and RAG scaffolding, but it also introduced integration mistakes such as filtering on the wrong status field, broad SSE payloads, an ownership edge case, a 502 on missing provider configuration, and hiding the draft after resolution. Human review, targeted tests, and live probes caught and corrected those issues.

Rate limiting is intentionally declined because it needs a store shared across workers. Test-suite expansion was implemented: the backend suite contains 39 tests covering authentication, ownership, classification, replies, metrics, notifications, and realtime publication.

## What I would do with more time

I would replace `migrate.py` with Alembic, move the SSE hub to Redis pub/sub for multi-worker deployment, add a real SMTP provider with delivery handling, add a PostgreSQL `pg_trgm` search index for titles, and add refresh-token rotation.

## Known issues / limitations

- The SSE hub is process-local and requires one worker. Events are invalidation signals; REST refetch is the recovery path.
- SSE accepts a query-param token for browser compatibility. Production should use HTTPS and short-lived access tokens.
- ChromaDB rebuilds when the server starts; there is no live knowledge-base refresh endpoint.
- The ticket title filter uses `ILIKE`, not a search index.
- Without `NVIDIA_API_KEY`, reply drafts use a degraded template grounded on retrieved KB excerpts, using lexical retrieval when the local embedding model is unavailable; the API returns HTTP 200 with `degraded: true`. Live NVIDIA drafting requires a configured key and reachable provider.
- JWTs are stored in localStorage and are not refreshable.
- CORS allows the local Vite origins (`http://localhost:5173` and `http://127.0.0.1:5173`) and the Compose UI origins (`http://localhost` and `http://127.0.0.1`). The event stream echoes `Access-Control-Allow-Origin` only for those origins.
- The console notifier is a mock backend and does not send external email.

## Pre-submission smoke checklist

Run this before recording the demo. Use `http://localhost:5173`, the seeded credentials above, and two browser profiles so both role sessions stay independent.

1. In the first profile, open `http://localhost:5173/login`, enter `employee@quickdesk.dev` / `Employee#Pass1`, click **Sign in**, open **New ticket**, enter title `VPN access request` and description `I need VPN access for a production incident`, then click **Submit ticket**. Expected: the ticket appears in **My tickets** with status **Open**.
2. In the second profile, open `http://localhost:5173/login`, sign in as `agent@quickdesk.dev` / `Agent#Pass1`, and open **Ticket dashboard**. Expected: the new ticket appears without refreshing the page, proving the `ticket_created` SSE invalidation.
3. Set the dashboard category filter to a category different from the new ticket's displayed category. Expected: the ticket disappears. Set the category filter back to **All categories**. Expected: it returns.
4. Open the ticket detail, click **Generate AI draft**, and wait for the draft. Expected: the textarea contains a draft and at least one citation chip is visible. If no NVIDIA key is configured, record the documented provider limitation instead of claiming this step passed.
5. Edit the draft textarea by adding a sentence, then click **Send reply**. Expected: the detail shows **Resolved** and the edited text is the final reply.
6. Return to **My tickets** in the employee profile. Expected: the ticket changes to **Resolved** without refreshing, proving the `ticket_resolved` SSE invalidation.
7. As the employee, submit a second ticket titled `Badge printer jam` with description `The lobby badge printer is jammed`. Seed data has users and articles only, so this is the other open ticket. In the agent profile, open that ticket from the dashboard without refreshing, change its category, and click **Save override**. Expected: **Overridden** appears, the original AI values remain visible, and **Override history** contains the agent entry.
8. Open `/metrics` as the agent. Expected: open/resolved counts reflect the actions, median resolution is present once a ticket is resolved, and override rate reflects the changed classification.
9. Stop Uvicorn with `Ctrl+C`, start it again with the documented one-worker command, and revisit both pages. Expected: both pages recover their state from REST without manual data repair.
10. Watch the backend console while resolving a ticket. Expected: one `---------- MOCK EMAIL ----------` block shows the employee recipient, subject, body, and closing delimiter.
11. Click **Log out** in both profiles, then click **Sign in** again with the same credentials. Expected: each role returns to its permitted workspace and cannot access the other role's navigation or protected endpoints.

## Where AI helped and where it hurt

AI sped up scaffolding (routes, React pages, KB markdown, test stubs) and produced a workable RAG + classification shape. Humans and tests had to fix several integration mistakes: the agent queue filtered on `ai_*` while the UI showed `final_*`, the SSE hub broadcast agent-only `ticket_created` payloads (including other employees' emails) to every connected client, employees were linked to an agent-only ticket route, drafts returned 502 when `NVIDIA_API_KEY` or the local MiniLM index was missing, and the agent ticket page hid the AI draft after resolve. Those are corrected in this tree. For a spoken walkthrough, use [docs/demo-outline.md](docs/demo-outline.md) — there is no demo video in the repository.

## Tested on

Fresh-clone verification on Windows, following the commands in this README:

- Python 3.12.10
- Node.js v24.19.0
- npm 11.17.0
- Docker Engine 29.8.1
- PostgreSQL 16.15
- Vite 6.4.3

`python -m pytest -q -p no:cacheprovider tests` from `backend` reported 39 passed with 3 deprecation warnings. `npm run build` completed successfully with Vite 6.4.3. `docker compose --profile full up --build -d` built and started PostgreSQL 16, the API, and nginx. `GET /api/health` returned `{"status":"ok"}`. The live seeded logins returned 200, bcrypt prefixes in PostgreSQL were `$2b$12$`, both seed passes were idempotent, the VPN draft returned non-empty citations, and the no-match draft explicitly reported no matching article. The browser checklist itself remains a human click-through.
