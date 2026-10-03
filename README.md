# QuickDesk

## What this is

QuickDesk Phase 1 is a small internal helpdesk foundation. It provides employee and agent accounts, bcrypt-backed password authentication, JWT sessions, backend role enforcement, a Postgres database, and a minimal React shell. Tickets, NVIDIA NIM, RAG, and sockets are intentionally deferred.

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
python seed.py
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The backend runs directly with Uvicorn for hot reload. Docker provides Postgres only. Alembic is deferred until a later phase; Phase 1 uses `create_all`.

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
```

## Decisions log

- I use the `bcrypt` package directly because passlib is unmaintained and its version detection breaks with bcrypt 4.x.
- I use PyJWT instead of python-jose because PyJWT has the clearer maintenance path for this small service and avoids python-jose's maintenance and CVE history concerns.
- I store the JWT in localStorage because this internal tool accepts the XSS exposure in exchange for avoiding CSRF; refresh and rotation remain known limitations. A SameSite=Lax cookie is the future alternative.
- I never allow public registration to create an agent. Privileged accounts come from seed or operations, not self-serve registration.
- I use `require_role()` as a dependency factory so authorization has one reusable choke point for every future route.
- I use `create_all` now because it is phase-appropriate for one table; Alembic and the resulting migration debt are deferred to a later phase.

If `JWT_SECRET_KEY` is empty in `QUICKDESK_ENV=dev`, startup generates a random local secret and logs a loud warning. Outside dev, startup raises instead. Never use the generated secret for production.

## Known issues / limitations

- There are no ticket, LLM, RAG, socket, refresh-token, or password-reset flows yet.
- JWTs are stored in localStorage and are not refreshable.
- CORS currently allows the local Vite origin only.
- Schema migrations are not yet managed by Alembic.
- Browser and production deployment verification are environment-dependent.

## Tested on

Python 3.12.10 and Node v24.19.0 (npm 11.17.0).
