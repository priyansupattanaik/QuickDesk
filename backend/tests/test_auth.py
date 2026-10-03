import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_quickdesk.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("QUICKDESK_ENV", "test")
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User, UserRole


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def override_get_db():
    with TestingSessionLocal() as db:
        yield db


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def register(email="person@example.com", password="Password1", full_name="Person"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "full_name": full_name})


def test_register_creates_employee_without_hash():
    response = register()
    assert response.status_code == 201
    assert response.json()["role"] == "employee"
    assert "password_hash" not in response.json()


def test_duplicate_email_returns_409():
    register()
    assert register().status_code == 409


def test_login_returns_jwt_claims():
    register()
    response = client.post("/api/auth/login", json={"email": "person@example.com", "password": "Password1"})
    assert response.status_code == 200
    claims = jwt.decode(response.json()["access_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert claims["sub"]
    assert claims["role"] == "employee"


def test_wrong_and_unknown_credentials_have_same_401_body():
    register()
    wrong = client.post("/api/auth/login", json={"email": "person@example.com", "password": "wrongpass"})
    unknown = client.post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrongpass"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def token_for(email="person@example.com", role="employee"):
    with TestingSessionLocal() as db:
        user = User(email=email, password_hash=hash_password("Password1"), full_name="Person", role=UserRole(role))
        db.add(user)
        db.commit()
        db.refresh(user)
        return create_access_token(str(user.id), role)


def test_me_with_valid_token():
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_for()}"})
    assert response.status_code == 200
    assert response.json()["email"] == "person@example.com"


def test_me_without_token_returns_401():
    assert client.get("/api/auth/me").status_code == 401


def test_employee_cannot_access_agent_summary():
    response = client.get("/api/agents/summary", headers={"Authorization": f"Bearer {token_for()}"})
    assert response.status_code == 403


def test_agent_can_access_agent_summary():
    response = client.get("/api/agents/summary", headers={"Authorization": f"Bearer {token_for('agent@example.com', 'agent')}"})
    assert response.status_code == 200
    assert response.json()["message"] == "Agent-only endpoint reachable"
