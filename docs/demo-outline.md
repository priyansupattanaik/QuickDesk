# QuickDesk demo script

Target length: 5–7 minutes. Record the browser and backend terminal together if possible. Use two browser profiles or two separate browser windows so the employee and agent sessions stay independent.

## Before recording

1. Start PostgreSQL, the backend, and the frontend using the [README setup instructions](../README.md).
2. Confirm that `http://localhost:5173` loads and that `http://127.0.0.1:8000/api/health` returns a healthy response.
3. Keep the backend terminal visible or ready to switch to. The resolution step prints a console mock email.
4. Sign in to one browser profile as the employee and another as the agent:

   - Employee: `employee@quickdesk.dev` / `Employee#Pass1`
   - Agent: `agent@quickdesk.dev` / `Agent#Pass1`

5. If `NVIDIA_API_KEY` is empty, the application still demonstrates ticket classification and a grounded degraded draft. Explain that the live provider response is optional; do not present the fallback as a live NVIDIA response.

## 0:00–0:35 — Product introduction

Show the QuickDesk sign-in page and say:

> “QuickDesk is an internal helpdesk. Employees submit support tickets, while agents classify, search, draft, resolve, and measure support work. The backend remains authoritative for authentication, ownership, classification, and resolution state.”

Briefly show the employee and agent workspaces. Do not spend time reading the implementation files during the opening.

## 0:35–1:30 — Employee creates a ticket

In the employee profile:

1. Open **New ticket**.
2. Enter:

   - Title: `VPN access request`
   - Description: `I need VPN access for a production incident`

3. Submit the ticket.
4. Show that it appears in **My tickets** with status **Open**.

Say:

> “The employee creates the ticket through the React client and FastAPI API. The backend stores the ticket and its AI-suggested classification, while the employee can see only the tickets allowed by the ownership rules.”

## 1:30–2:20 — Live agent update

Switch to the agent profile and open **Ticket dashboard**.

Show that the new ticket appears without manually refreshing the page. Say:

> “The agent dashboard received a `ticket_created` Server-Sent Event. SSE is only an invalidation signal; the frontend refetches the authoritative ticket list through REST.”

Open the ticket detail and point out:

- Original AI category and priority.
- Confidence, when available.
- Editable final category and priority.
- The **Save classification** action.

If useful, change the category or priority and save it. Show the audit history afterward. Explain:

> “The original AI values remain visible, while the agent’s final decision and audit entry are stored separately.”

## 2:20–3:25 — Grounded draft and citations

On the ticket detail page:

1. Click **Generate AI draft**.
2. Wait for the draft and citation list.
3. Point to the citation titles and, if time permits, open one source article.
4. Add a short sentence to the draft textarea.

Say:

> “The backend retrieves relevant knowledge-base excerpts, validates the citations against PostgreSQL, and saves the draft with its evidence. The system can use local Chroma and MiniLM retrieval, with a lexical fallback when the embedding model is unavailable.”

If the screen shows a degraded draft, say:

> “This environment has no NVIDIA API key, so the application is using its grounded fallback. The fallback is intentional: it keeps the workflow usable without inventing a provider response or unsupported citations.”

## 3:25–4:20 — Resolve the ticket and show notification

Click **Send reply**.

Show that:

- The ticket status changes to **Resolved**.
- The edited text is the final reply.
- The backend terminal prints one `---------- MOCK EMAIL ----------` block.

Say:

> “The resolution is committed before the notification is attempted. The console notifier is a mock email backend for this demo; a notification failure cannot roll back an already committed resolution.”

Switch back to the employee profile and show that **My tickets** updates to **Resolved** without a manual refresh. Explain that this is the `ticket_resolved` SSE invalidation followed by a REST refetch.

## 4:20–5:05 — Metrics and access control

Switch to the agent profile and open **Metrics**. Point out:

- Open and resolved counts.
- Category counts.
- Median resolution time after resolving a ticket.
- Classification override rate if you saved an override.

Say:

> “Metrics are calculated by the backend from PostgreSQL data. The frontend does not decide what a user is allowed to see.”

Optionally try an employee-only view or sign out and sign back in to show that the role-specific navigation and backend authorization remain enforced.

## 5:05–5:45 — Architecture summary

Show the README architecture section or a simple diagram while saying:

> “React and Vite provide the browser application. FastAPI handles REST and SSE. SQLAlchemy persists users, tickets, classifications, replies, and audit history in PostgreSQL. Chroma and local embeddings support knowledge retrieval. The frontend uses SSE for refresh signals and REST for the source of truth.”

Mention the important operational constraint:

> “The current SSE hub is process-local, so the backend runs with one Uvicorn worker. A multi-worker production deployment would use a shared broker such as Redis.”

## Optional 30-second closing

Show the login page or dashboard and close with:

> “The complete workflow is employee submission, real-time agent intake, grounded drafting with citations, auditable classification, durable resolution, notification, and employee-side confirmation.”

## Claims to avoid

- Do not claim that an NVIDIA response was used when `NVIDIA_API_KEY` is empty.
- Do not claim that the browser flow was automated; it is a human click-through demo.
- Do not claim that the console mock email sends external email.
- Do not run host Uvicorn and the containerized backend on port `8000` at the same time.
