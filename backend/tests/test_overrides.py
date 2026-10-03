import os
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_quickdesk.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("QUICKDESK_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import OverrideLog, Ticket, User, UserRole
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
        db.add_all([employee, agent])
        db.commit()
        return employee.id, agent.id


def headers(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(str(user_id), role)}"}


def ticket(employee_id):
    response = client.post("/api/tickets", headers=headers(employee_id, "employee"), json={"title": "Access", "description": "Need access"})
    assert response.status_code == 201
    return response.json()["id"]


def logs(ticket_id):
    with TestingSessionLocal() as db:
        return db.scalars(select(OverrideLog).where(OverrideLog.ticket_id == UUID(ticket_id)).order_by(OverrideLog.created_at.desc())).all()


def test_category_override_logs_without_changing_ai_value():
    employee_id, agent_id = users(); ticket_id = ticket(employee_id)
    response = client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(agent_id, "agent"), json={"final_category": "HR"})
    assert response.status_code == 200
    assert response.json()["final_category"] == "HR"
    assert response.json()["ai_category"] == "IT"
    entry = logs(ticket_id)[0]
    assert (entry.field, entry.from_value, entry.to_value, entry.agent_id) == ("category", "IT", "HR", agent_id)


def test_priority_override_only_logs_priority():
    employee_id, agent_id = users(); ticket_id = ticket(employee_id)
    client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(agent_id, "agent"), json={"final_priority": "Low"})
    entries = logs(ticket_id)
    assert len(entries) == 1 and entries[0].field == "priority"


def test_same_value_creates_no_log():
    employee_id, agent_id = users(); ticket_id = ticket(employee_id)
    response = client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(agent_id, "agent"), json={"final_category": "IT"})
    assert response.status_code == 200 and logs(ticket_id) == []


def test_both_overrides_create_two_logs():
    employee_id, agent_id = users(); ticket_id = ticket(employee_id)
    client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(agent_id, "agent"), json={"final_category": "Finance", "final_priority": "Low"})
    assert {entry.field for entry in logs(ticket_id)} == {"category", "priority"}


def test_employee_and_unauthenticated_cannot_override():
    employee_id, agent_id = users(); ticket_id = ticket(employee_id)
    assert client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(employee_id, "employee"), json={"final_category": "HR"}).status_code == 403
    assert client.patch(f"/api/tickets/{ticket_id}/classification", json={"final_category": "HR"}).status_code == 401
    assert client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(agent_id, "agent"), json={"final_category": "Bad"}).status_code == 422


def test_detail_contains_newest_first_audit_log_and_agent_identity():
    employee_id, agent_id = users(); ticket_id = ticket(employee_id)
    client.patch(f"/api/tickets/{ticket_id}/classification", headers=headers(agent_id, "agent"), json={"final_category": "HR", "final_priority": "Low"})
    detail = client.get(f"/api/tickets/{ticket_id}", headers=headers(agent_id, "agent"))
    assert detail.status_code == 200
    assert len(detail.json()["audit_log"]) == 2
    assert detail.json()["audit_log"][0]["agent"]["email"] == "agent@example.com"
