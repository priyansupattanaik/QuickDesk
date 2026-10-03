# QuickDesk

## What this is

QuickDesk is a small internal helpdesk. Phase 2 adds employee ticket submission, NVIDIA-assisted classification with a safe fallback, agent filtering, and grounded reply drafts over a seeded knowledge base. The backend remains the authority for roles and ownership.

## Local run

From a fresh clone, run:

```bash
docker compose up -d
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cp .env.example .env       # PowerShell: Copy-Item .env.example .env
openssl rand -hex 32       # put the result in JWT_SECRET_KEY in .env
cd backend
python migrate.py
python seed.py
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The backend runs directly with Uvicorn. Docker provides Postgres only. Run `migrate.py` before `seed.py` on an existing database; it is safe to run repeatedly. The SSE hub is in-process, so use one worker. `seed.py` also loads the six markdown knowledge-base articles and is safe to run repeatedly.

## Architecture

```text
Browser
  | React UI + localStorage JWT
  v
React/Vite :5173 -- Authorization: Bearer <JWT> --> FastAPI :8000
                                                        |
                                                        | SQLAlchemy / DATABASE_URL
                                                        v
                                                   Postgres :5432

login -> signed JWT (sub=user id, role, exp) -> protected API dependency
agent -> `/api/events?token=...` -> in-process SSE hub -> ticket invalidation event
agent -> `/api/metrics` -> SQL aggregates and Postgres `percentile_cont` median
```

## Phase 2

### RAG pipeline

The six seeded articles are split with `RecursiveCharacterTextSplitter` at 500 characters with 50 characters of overlap. The corpus is intentionally small, so one or two useful chunks per article is preferable to fragmenting a short policy into pieces too small to retrieve. Embeddings use the local `sentence-transformers/all-MiniLM-L6-v2` model. NVIDIA embeddings would add a network dependency and cost to a corpus this size without improving the operating model.

The vector store is a local ChromaDB collection rebuilt during startup, with a retriever configured for `k=3` and a small relevance threshold. Chroma keeps the collection and metadata in the ignored `backend/chroma_db` directory, but the application still rebuilds it so knowledge-base edits are picked up honestly on restart. There is no index rebuild endpoint. `services/rag.py` owns loading, chunking, retrieval, and citations. `services/llm.py` owns the prompts and NVIDIA calls. The reply prompt says to use only the supplied excerpts and to admit when none are relevant. An empty retrieval still reaches the model with an explicit no-excerpts instruction.

### NVIDIA NIM

The model is read from `NVIDIA_MODEL`. The OpenAI SDK talks to NVIDIA through `NVIDIA_BASE_URL`, so changing the provider is an environment configuration change rather than a second client implementation. NVIDIA free-tier rate limits are a known operational constraint. Ticket creation never depends on the provider: timeout, provider, parse, and validation failures store `Other`/`Medium` with `ai_classified=false`.

Classification asks for strict JSON, extracts the first JSON object, validates both values, retries once with an invalid-response instruction, then falls back plainly to `Other`/`Medium`.

### API additions

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| POST | `/api/tickets` | Create and classify a ticket | employee or agent |
| GET | `/api/tickets/mine` | List the signed-in employee's tickets | employee or agent |
| GET | `/api/tickets` | Filtered, paginated agent queue | agent |
| GET | `/api/tickets/{id}` | Ticket detail with ownership guard | agent or owning employee |
| POST | `/api/tickets/{id}/ai-draft` | Retrieve citations and save a draft | agent |
| POST | `/api/tickets/{id}/reply` | Persist final reply and resolve ticket | agent |
| PATCH | `/api/tickets/{id}/classification` | Override final category and/or priority | agent |
| GET | `/api/tickets/{id}` | Return AI values, final values, and override audit history | agent or owning employee |
| GET | `/api/events?token=...` | Stream ticket-created/resolved invalidation events | authenticated user |
| GET | `/api/metrics` | Return agent-only status, category, median, and override metrics | agent |

### Decisions log

- I use local MiniLM embeddings rather than NVIDIA-hosted embeddings because the six-article corpus does not justify another network dependency.
- I use local ChromaDB because it preserves document metadata and gives the small app a durable collection without adding a service; startup rebuild remains the refresh mechanism.
- I use plain `WHERE` predicates and `ILIKE` for the queue because they are easy to inspect; a trigram index can be added if ticket volume grows.
- I persist `ai_draft` and `final_reply` separately because the next phase needs to compare what the model suggested with what the agent sent.
- Phase 2 shipped with FAISS; I switched to ChromaDB before Phase 3. Reason: Chroma's collection API is cleaner than managing FAISS index files by hand, its local mode gives a directory-backed store with no server process, and at this corpus size the retrieval behavior is identical. The swap touched only services/rag.py; embeddings stayed local MiniLM; the restart-to-refresh index limitation is unchanged.
- I keep `ai_category`/`ai_priority` as immutable model output and store agent choices in `final_category`/`final_priority`. This makes the metric row data explicit and keeps every change auditable in `override_logs`.
- I use a hand-written `migrate.py` for this phase because the schema change is limited to two columns and one table; Alembic remains a later operational improvement.
- I use a query-parameter JWT for the internal SSE endpoint because browser `EventSource` cannot set an Authorization header. Production deployment must use HTTPS and short-lived tokens.
- I use an in-process SSE hub with one Uvicorn worker for this phase. A multi-worker deployment needs Redis pub/sub or another shared broker.
- SSE events are invalidation signals only. The frontend refetches REST data on open and on each event, so REST remains the source of truth and reconnects cannot silently lose state.

Without `NVIDIA_API_KEY`, the app still starts and ticket creation still returns `201`; classification and drafting use the provider only when called, with classification falling back to `ai_classified=false`. A real draft requires a working provider key.
## Earlier decisions log

- I use the `bcrypt` package directly because passlib is unmaintained and its version detection breaks with bcrypt 4.x.
- I use PyJWT instead of python-jose because PyJWT has the clearer maintenance path for this small service and avoids python-jose's maintenance and CVE history concerns.
- I store the JWT in localStorage because this internal tool accepts the XSS exposure in exchange for avoiding CSRF; refresh and rotation remain known limitations. A SameSite=Lax cookie is the future alternative.
- I never allow public registration to create an agent. Privileged accounts come from seed or operations, not self-serve registration.
- I use `require_role()` as a dependency factory so authorization has one reusable choke point for every future route.

If `JWT_SECRET_KEY` is empty in `QUICKDESK_ENV=dev`, startup generates a random local secret and logs a loud warning. Outside dev, startup raises instead. Never use the generated secret for production.

## Known issues / limitations

- SSE is intentionally limited to ticket-created and ticket-resolved invalidation events; it is not a general-purpose socket protocol.
- The SSE hub is process-local and requires one worker. Redis pub/sub is the upgrade path for multiple workers.
- ChromaDB is rebuilt only when the server starts; there is no live KB refresh.
- Agent filters use `ILIKE` rather than a search index.
- JWTs are stored in localStorage and are not refreshable.
- CORS currently allows the local Vite origin only.
- `migrate.py` is the schema migration path for this phase; Alembic is not yet managed.
- Browser and production deployment verification are environment-dependent.

## Tested on

Python 3.12.10 and Node v24.19.0 (npm 11.17.0). Phase 1, Phase 2, and Phase 3 backend tests pass locally; browser interaction and the manual SSE smoke remain environment checks.
