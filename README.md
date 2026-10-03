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

**Knowledge base index and embeddings (first run):** On startup, `backend/app/main.py` calls `rebuild_index()`, which reads seeded KB articles from Postgres and writes a local Chroma collection under `backend/chroma_db/` (gitignored). The first successful run downloads `sentence-transformers/all-MiniLM-L6-v2` into your Hugging Face cache (~90MB). If the model or index is missing, retrieval returns no chunks and drafts still succeed in degraded mode. Re-run `python seed.py` then restart Uvicorn to rebuild after an empty database.

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
| POST | `/api/tickets` | Create and classify a ticket | Employee or agent |
| GET | `/api/tickets/mine` | List the signed-in employee's tickets | Employee or agent |
| GET | `/api/tickets` | Filter and paginate the agent queue | Agent |
| GET | `/api/tickets/{id}` | Return ticket detail and audit history | Agent or owning employee |
| PATCH | `/api/tickets/{id}/classification` | Override final category and/or priority | Agent |
| POST | `/api/tickets/{id}/ai-draft` | Retrieve citations and save an AI draft | Agent |
| POST | `/api/tickets/{id}/reply` | Save final reply and resolve the ticket | Agent |

## Decisions and tradeoffs

- I use ChromaDB in local persistent mode instead of FAISS because this six-article corpus needs a directory-backed collection and document metadata without another service. The retrieval behavior remains local and the index is rebuilt on startup.
- I use `sentence-transformers/all-MiniLM-L6-v2` locally. I use `RecursiveCharacterTextSplitter` with 500-character chunks and 50-character overlap, then retrieve `k=3` chunks with a `0.2` similarity threshold.
- I use NVIDIA NIM through the OpenAI-compatible client with the configured `meta/llama-3.2-11b-vision-instruct` model. Provider, parse, timeout, and validation failures fall back to `Other`/`Medium` and never block ticket creation.
- I keep `ai_category` and `ai_priority` as the original model output and store agent decisions in `final_category` and `final_priority`. `override_logs` records each changed field, old value, new value, agent, and timestamp.
- I use the `bcrypt` package directly. passlib is unmaintained, and its version check breaks against bcrypt 4.x.
- I use PyJWT instead of python-jose. python-jose has the weaker maintenance path and the CVE history I did not want in this service. Access tokens expire after 60 minutes.
- I store the JWT in localStorage. For this internal tool I accept the XSS exposure in exchange for avoiding CSRF. Refresh tokens and rotation remain future work. The backend still verifies every role and ownership decision.
- Public registration can only create an employee. Agent accounts come from seed or operations, never from self-serve signup.
- I use `require_role()` as a dependency factory so every protected route shares one authorization choke point.
- I use query-param JWT authentication for SSE because browser `EventSource` cannot set an Authorization header. I run one Uvicorn worker because the hub is in-process; Redis pub/sub is required for multiple workers.
- I use SQL aggregates and PostgreSQL `percentile_cont(0.5)` for median resolution time. Override rate uses null-safe `IS DISTINCT FROM`, so fallback/null values do not create false overrides.
- I use a hand-written `migrate.py` for the additive final-classification columns and `override_logs` table. The change is small enough that Alembic can wait.
- I use `EMAIL_BACKEND=console` for the one selected stretch goal. The notifier builds a real plain-text resolution email and logs it after commit; SMTP is a documented swap, not an unimplemented claim.

I deliberately declined the other stretch goals: Dockerizing the full application adds deployment scope beyond the requested local Postgres container; AI confidence needs a reliable calibrated signal; rate limiting needs a deployment-wide store; and test-suite expansion is not a product feature for this phase.

## What I would do with more time

I would replace `migrate.py` with Alembic, move the SSE hub to Redis pub/sub for multi-worker deployment, add a real SMTP provider with delivery handling, add a PostgreSQL `pg_trgm` search index for titles, and add refresh-token rotation.

## Known issues / limitations

- The SSE hub is process-local and requires one worker. Events are invalidation signals; REST refetch is the recovery path.
- SSE accepts a query-param token for browser compatibility. Production should use HTTPS and short-lived access tokens.
- ChromaDB rebuilds when the server starts; there is no live knowledge-base refresh endpoint.
- The ticket title filter uses `ILIKE`, not a search index.
- Without `NVIDIA_API_KEY`, reply drafts use a template grounded on retrieved KB excerpts when available; the API returns HTTP 200 with `degraded: true`. Live NVIDIA drafting requires a configured key and reachable provider.
- JWTs are stored in localStorage and are not refreshable.
- CORS currently allows the local Vite origin only.
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

`python -m pytest -q -p no:cacheprovider tests` from `backend` in that virtual environment reported 34 passed. `npm run build` completed. One Uvicorn worker reached `Application startup complete`, loaded the local MiniLM weights, and `GET /api/health` returned 200. `npm run dev` served `http://127.0.0.1:5173/` with 200. The seeded employee login returned 200. The browser checklist above was not clicked through.
