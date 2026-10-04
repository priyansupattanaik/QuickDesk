import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")
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
from app.models import Ticket, TicketStatus, User, UserRole

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
def database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def setup_users():
    with TestingSessionLocal() as db:
        employee = User(email="employee@example.com", password_hash=hash_password("Password1"), full_name="Employee", role=UserRole.employee)
        agent = User(email="agent@example.com", password_hash=hash_password("Password1"), full_name="Agent", role=UserRole.agent)
        db.add_all([employee, agent]); db.commit()
        return employee.id, agent.id


def auth(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(str(user_id), role)}"}


def add_tickets(employee_id):
    base = datetime.now(timezone.utc) - timedelta(hours=10)
    with TestingSessionLocal() as db:
        values = [(TicketStatus.open, "IT", "IT", None), (TicketStatus.resolved, "HR", "Finance", 1), (TicketStatus.resolved, "HR", "HR", 3), (TicketStatus.resolved, "Finance", "Finance", 5)]
        for index, (status, ai_category, final_category, hours) in enumerate(values):
            created = base + timedelta(minutes=index)
            db.add(Ticket(employee_id=employee_id, title=f"Ticket {index}", description="Details", status=status, ai_category=ai_category, ai_priority="Medium", ai_classified=True, final_category=final_category, final_priority="Medium", created_at=created, resolved_at=created + timedelta(hours=hours) if hours else None))
        db.commit()


def test_metrics_counts_group_by_final_category_and_status():
    employee_id, agent_id = setup_users(); add_tickets(employee_id)
    response = client.get("/api/metrics", headers=auth(agent_id, "agent"))
    assert response.status_code == 200
    data = response.json()
    assert data["by_status"] == {"Open": 1, "Resolved": 3}
    assert sorted(data["by_category"], key=lambda row: row["category"]) == [{"category": "Finance", "count": 2}, {"category": "HR", "count": 1}, {"category": "IT", "count": 1}]


def test_metrics_median_and_override_rate():
    employee_id, agent_id = setup_users(); add_tickets(employee_id)
    data = client.get("/api/metrics", headers=auth(agent_id, "agent")).json()
    assert data["median_resolution_seconds"] == pytest.approx(10800.0, abs=1)
    assert data["override_rate_percent"] == 25.0


def test_empty_metrics_returns_nulls_and_employee_is_forbidden():
    employee_id, agent_id = setup_users()
    data = client.get("/api/metrics", headers=auth(agent_id, "agent")).json()
    assert data["median_resolution_seconds"] is None and data["override_rate_percent"] is None
    assert client.get("/api/metrics", headers=auth(employee_id, "employee")).status_code == 403
