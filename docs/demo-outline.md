# QuickDesk demo outline

Target length: 3–5 minutes. Use two browser profiles and the seeded credentials in the README. Keep the backend terminal visible for the mock email block.

## 0:00–0:30 — What it is and run

Say: “QuickDesk is an internal helpdesk where employees submit tickets and agents resolve them with grounded AI assistance, live updates, and auditable classification.”

Show the README run commands, then the employee login at `http://localhost:5173`. The API is FastAPI in `backend/app/main.py`; the frontend is Vite in `frontend`.

## 0:30–2:00 — Live flow

1. In the employee profile, submit a ticket from `/tickets/new`. This calls `POST /api/tickets` in `backend/app/routers/tickets.py`.
2. Switch to the agent profile at `/dashboard`. The ticket appears without refresh because `POST /api/tickets` publishes `ticket_created` through `backend/app/realtime.py`, and `frontend/src/realtime/useTicketEvents.js` refetches the queue.
3. Open the ticket and click **Generate AI draft**. This calls `POST /api/tickets/{id}/ai-draft`; `backend/app/services/rag.py` retrieves three ChromaDB-backed MiniLM matches and returns citation metadata.
4. Point out the citation chips, edit the textarea, and click **Send reply**. This calls `POST /api/tickets/{id}/reply`, commits `final_reply` and `Resolved`, publishes `ticket_resolved`, and invokes `backend/app/services/notifier.py`.
5. Return to the employee profile. `GET /api/tickets/mine` is refetched after the SSE event, so the ticket becomes **Resolved** without a browser refresh.
6. Keep the backend terminal visible and show the `---------- MOCK EMAIL ----------` block with the employee recipient, subject, final reply, and sign-off.

## 2:00–3:30 — Architecture

Spend one minute on the request flow: React sends REST requests to FastAPI; `backend/app/core/deps.py` enforces JWT roles and ownership; SQLAlchemy persists tickets, AI values, final values, and `override_logs` in Postgres.

Spend 30 seconds on RAG: `backend/app/services/rag.py` uses 500-character chunks with 50-character overlap, local `sentence-transformers/all-MiniLM-L6-v2`, ChromaDB persistence, `k=3`, and a `0.2` relevance threshold. `backend/app/services/llm.py` sends only the retrieved excerpts to NVIDIA NIM.

Spend 30 seconds on SSE: `GET /api/events?token=...` is an in-process one-worker hub. Events are invalidation signals, and the frontend refetches REST data on connection open and event receipt. This keeps REST authoritative and makes reconnects recoverable; Redis pub/sub is the multi-worker upgrade.

## 3:30–4:00 — Decisions and limitation

Say: “The two decisions I’m proudest of are preserving immutable AI classification beside agent-owned final classification with an audit trail, and using SSE only as a refetch signal so the backend remains authoritative.”

State one limitation honestly: “The current SSE hub is process-local and requires one worker. A production multi-worker deployment needs Redis pub/sub.”

If there is time, show `/metrics`, backed by `GET /api/metrics`, and point out the Postgres `percentile_cont` median and null-safe override rate.
