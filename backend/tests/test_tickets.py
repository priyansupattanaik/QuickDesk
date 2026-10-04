import os
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("QUICKDESK_ENV", "test")

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Ticket, User, UserRole
from app.routers import tickets as tickets_router
from app.services import llm

# The router imports service functions directly; monkeypatch those imported names at the API seam.
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


def auth_users():
    with TestingSessionLocal() as db:
        employee = User(email="employee@example.com", password_hash=hash_password("Password1"), full_name="Employee", role=UserRole.employee)
        other = User(email="other@example.com", password_hash=hash_password("Password1"), full_name="Other", role=UserRole.employee)
        agent = User(email="agent@example.com", password_hash=hash_password("Password1"), full_name="Agent", role=UserRole.agent)
        db.add_all([employee, other, agent])
        db.commit()
        return employee.id, other.id, agent.id


def token(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(str(user_id), role)}"}


@pytest.fixture(autouse=True)
def no_network_classifier(monkeypatch):
    monkeypatch.setattr(tickets_router, "classify_ticket", lambda *_: {"category": "Other", "priority": "Medium", "fallback": False})


def setup_function():
    Base.metadata.create_all(engine)
    with TestingSessionLocal() as db:
        db.query(Ticket).delete()
        db.query(User).delete()
        db.commit()


def teardown_function():
    Base.metadata.drop_all(engine)


def test_employee_creates_ticket_with_classifier(monkeypatch):
    employee_id, _, _ = auth_users()
    monkeypatch.setattr(tickets_router, "classify_ticket", lambda *_: {"category": "IT", "priority": "High", "fallback": False})
    response = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "VPN issue", "description": "VPN will not connect"})
    assert response.status_code == 201
    assert response.json()["ai_category"] == "IT"
    assert response.json()["ai_priority"] == "High"
    assert response.json()["ai_classified"] is True


def test_classifier_garbage_retries_then_falls_back(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "garbage"})()})()]})()

    monkeypatch.setattr(llm.settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(llm.client, "chat", type("Chat", (), {"completions": FakeCompletions()})())
    assert llm.classify_ticket("Unknown", "No details") == {"category": "Other", "priority": "Medium", "fallback": True}


def test_classifier_exception_does_not_fail_creation(monkeypatch):
    employee_id, _, _ = auth_users()
    def fail(*_):
        raise TimeoutError("provider unavailable")
    monkeypatch.setattr(tickets_router, "classify_ticket", fail)
    response = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Access", "description": "Cannot open drive"})
    assert response.status_code == 201
    assert response.json()["ai_category"] == "Other"
    assert response.json()["ai_priority"] == "Medium"
    assert response.json()["ai_classified"] is False


def test_employee_mine_returns_only_own_tickets(monkeypatch):
    employee_id, other_id, _ = auth_users()
    monkeypatch.setattr(tickets_router, "classify_ticket", lambda *_: {"category": "Other", "priority": "Medium", "fallback": False})
    client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Mine", "description": "A"})
    client.post("/api/tickets", headers=token(other_id, "employee"), json={"title": "Other", "description": "B"})
    response = client.get("/api/tickets/mine", headers=token(employee_id, "employee"))
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Mine"]


def test_employee_cannot_list_agent_tickets():
    employee_id, _, _ = auth_users()
    assert client.get("/api/tickets", headers=token(employee_id, "employee")).status_code == 403


def test_agent_queue_filters_use_final_classification(monkeypatch):
    employee_id, _, agent_id = auth_users()
    monkeypatch.setattr(tickets_router, "classify_ticket", lambda *_: {"category": "IT", "priority": "High", "fallback": False})
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "VPN", "description": "Need VPN"}).json()
    client.patch(
        f"/api/tickets/{created['id']}/classification",
        headers=token(agent_id, "agent"),
        json={"final_category": "HR"},
    )
    assert client.get("/api/tickets?category=HR", headers=token(agent_id, "agent")).json()["total"] == 1
    assert client.get("/api/tickets?category=IT", headers=token(agent_id, "agent")).json()["total"] == 0


def test_agent_filters_search_and_pagination(monkeypatch):
    _, employee_id, agent_id = auth_users()
    monkeypatch.setattr(tickets_router, "classify_ticket", lambda title, *_: {"category": "IT" if "VPN" in title else "HR", "priority": "High", "fallback": False})
    for title in ["VPN access", "Leave policy", "VPN laptop"]:
        client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": title, "description": title})
    response = client.get("/api/tickets?category=IT&q=vPn&page=1&page_size=1", headers=token(agent_id, "agent"))
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1


def test_employee_ownership_guard():
    employee_id, other_id, agent_id = auth_users()
    response = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Private", "description": "Details"})
    ticket_id = response.json()["id"]
    assert client.get(f"/api/tickets/{ticket_id}", headers=token(other_id, "employee")).status_code == 403
    assert client.get(f"/api/tickets/{ticket_id}", headers=token(employee_id, "employee")).status_code == 200
    assert client.get(f"/api/tickets/{ticket_id}", headers=token(agent_id, "agent")).status_code == 200


def test_agent_draft_persists_citations(monkeypatch):
    employee_id, _, agent_id = auth_users()
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "VPN", "description": "Need VPN"}).json()
    monkeypatch.setattr(tickets_router, "get_relevant_chunks", lambda _: [type("Doc", (), {"page_content": "VPN steps", "metadata": {"article_id": "a1", "title": "VPN"}})()])
    monkeypatch.setattr(tickets_router, "citations_for", lambda _: [{"article_id": "a1", "title": "VPN"}])
    monkeypatch.setattr(tickets_router, "generate_reply", lambda *_: "Follow the VPN steps.")
    response = client.post(f"/api/tickets/{created['id']}/ai-draft", headers=token(agent_id, "agent"))
    assert response.status_code == 200
    assert response.json() == {"ai_draft": "Follow the VPN steps.", "citations": [{"article_id": "a1", "title": "VPN"}], "degraded": False}
    detail = client.get(f"/api/tickets/{created['id']}", headers=token(agent_id, "agent")).json()
    assert detail["ai_citations"] == response.json()["citations"]


def test_ai_draft_degrades_without_provider(monkeypatch):
    employee_id, _, agent_id = auth_users()
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "VPN", "description": "Need VPN"}).json()
    monkeypatch.setattr(tickets_router, "get_relevant_chunks", lambda _: [])
    monkeypatch.setattr(tickets_router, "citations_for", lambda _: [])

    def fail_generate(*_):
        raise RuntimeError("NVIDIA_API_KEY is not configured")

    monkeypatch.setattr(tickets_router, "generate_reply", fail_generate)
    response = client.post(f"/api/tickets/{created['id']}/ai-draft", headers=token(agent_id, "agent"))
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["ai_draft"]
    assert "NVIDIA" in body["ai_draft"]


def test_empty_retrieval_still_returns_draft(monkeypatch):
    employee_id, _, agent_id = auth_users()
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Unknown", "description": "Unknown"}).json()
    monkeypatch.setattr(tickets_router, "get_relevant_chunks", lambda _: [])
    monkeypatch.setattr(tickets_router, "citations_for", lambda _: [])
    monkeypatch.setattr(tickets_router, "generate_reply", lambda *_: "I don't have a specific article for this issue.")
    response = client.post(f"/api/tickets/{created['id']}/ai-draft", headers=token(agent_id, "agent"))
    assert response.status_code == 200
    assert response.json()["citations"] == []
    assert response.json()["ai_draft"]


def test_agent_reply_resolves_and_preserves_draft():
    employee_id, _, agent_id = auth_users()
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Reply", "description": "Need help"}).json()
    with TestingSessionLocal() as db:
        ticket = db.get(Ticket, UUID(created["id"]))
        ticket.ai_draft = "Draft reply"
        ticket.ai_citations = []
        db.commit()
    response = client.post(f"/api/tickets/{created['id']}/reply", headers=token(agent_id, "agent"), json={"reply_text": "Final reply"})
    assert response.status_code == 200
    assert response.json()["status"] == "Resolved"
    assert response.json()["resolved_at"]
    assert response.json()["ai_draft"] == "Draft reply"
    assert response.json()["final_reply"] == "Final reply"


def test_second_reply_returns_409():
    employee_id, _, agent_id = auth_users()
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Reply", "description": "Need help"}).json()
    client.post(f"/api/tickets/{created['id']}/reply", headers=token(agent_id, "agent"), json={"reply_text": "Done"})
    response = client.post(f"/api/tickets/{created['id']}/reply", headers=token(agent_id, "agent"), json={"reply_text": "Again"})
    assert response.status_code == 409


def test_employee_cannot_reply():
    employee_id, _, _ = auth_users()
    created = client.post("/api/tickets", headers=token(employee_id, "employee"), json={"title": "Reply", "description": "Need help"}).json()
    assert client.post(f"/api/tickets/{created['id']}/reply", headers=token(employee_id, "employee"), json={"reply_text": "Done"}).status_code == 403
