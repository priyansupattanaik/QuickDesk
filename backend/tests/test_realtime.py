import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_quickdesk.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("QUICKDESK_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User, UserRole
from app.routers import tickets as tickets_router

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    with TestingSessionLocal() as db:
        yield db


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def app_database_override():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(autouse=True)
def database(monkeypatch):
    Base.metadata.create_all(engine)
    monkeypatch.setattr(tickets_router, "classify_ticket", lambda *_: {"category": "IT", "priority": "High", "fallback": False})
    yield
    Base.metadata.drop_all(engine)


def users():
    with TestingSessionLocal() as db:
        employee = User(email="employee@example.com", password_hash=hash_password("Password1"), full_name="Employee", role=UserRole.employee)
        agent = User(email="agent@example.com", password_hash=hash_password("Password1"), full_name="Agent", role=UserRole.agent)
        db.add_all([employee, agent]); db.commit()
        return employee.id, agent.id


def auth(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(str(user_id), role)}"}


def test_events_reject_missing_and_garbage_tokens():
    assert client.get("/api/events").status_code == 401
    assert client.get("/api/events?token=garbage").status_code == 401


def test_ticket_create_and_reply_publish_events(monkeypatch):
    employee_id, agent_id = users(); captured = []
    async def capture(channel, event, data):
        captured.append((channel, event, data))
    monkeypatch.setattr(tickets_router, "publish", capture)
    created = client.post("/api/tickets", headers=auth(employee_id, "employee"), json={"title": "New", "description": "Details"}).json()
    client.post(f"/api/tickets/{created['id']}/reply", headers=auth(agent_id, "agent"), json={"reply_text": "Done"})
    assert captured[0][0:2] == ("agents", "ticket_created") and captured[0][2]["id"] == created["id"]
    assert captured[1][0:2] == (f"user:{employee_id}", "ticket_resolved")


def test_authenticated_event_stream_starts_with_heartbeat():
    employee_id, _ = users()
    token = create_access_token(str(employee_id), "employee")
    from app.routers.events import events
    from starlette.requests import Request

    request = Request({"type": "http", "method": "GET", "path": "/api/events", "headers": [], "query_string": b""})
    response = asyncio.run(events(request, token, next(override_get_db())))
    iterator = response.body_iterator
    assert asyncio.run(iterator.__anext__()) == ": heartbeat\n\n"
    asyncio.run(iterator.aclose())
