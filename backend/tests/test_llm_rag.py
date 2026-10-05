import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("QUICKDESK_ENV", "test")

from app.config import settings
from app.services.llm import (
    DEFAULT_MODEL,
    _resolve_model,
    _chat_completion,
    classify_ticket,
    generate_degraded_draft,
    generate_reply,
    is_supported_reply,
)
from app.models import Ticket


def test_resolve_model():
    assert _resolve_model("meta/llama-3.3-70b-instruct") == DEFAULT_MODEL
    assert _resolve_model("") == DEFAULT_MODEL
    assert _resolve_model("custom-model") == "custom-model"


def test_chat_completion_status_error_fallback(monkeypatch):
    calls = []

    class DummyAPIError(Exception):
        def __init__(self, status_code):
            self.status_code = status_code

    class DummyCompletions:
        def create(self, model, messages, **kwargs):
            calls.append(model)
            if model != DEFAULT_MODEL:
                raise DummyAPIError(410)
            return type("Choice", (), {"choices": [type("Msg", (), {"message": type("Content", (), {"content": "Fallback OK"})()})()]})()

    from app.services import llm
    monkeypatch.setattr(llm.client, "chat", type("Chat", (), {"completions": DummyCompletions()})())
    monkeypatch.setattr(settings, "nvidia_model", "some-deprecated-model")

    result = _chat_completion([{"role": "user", "content": "Hi"}])
    assert result == "Fallback OK"
    assert calls == ["some-deprecated-model", DEFAULT_MODEL]


def test_classify_ticket_without_key(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    res = classify_ticket("Title", "Description")
    assert res["fallback"] is True
    assert res["category"] == "Other"


def test_generate_reply_without_key(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    t = Ticket(title="VPN", description="Help")
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY is not configured"):
        generate_reply(t, [])


def test_degraded_draft_messages(monkeypatch):
    t = Ticket(title="Printer", description="Jam")
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    draft_no_key = generate_degraded_draft(t, [])
    assert "configure NVIDIA_API_KEY" in draft_no_key
    assert "NVIDIA" in draft_no_key

    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")
    draft_with_key = generate_degraded_draft(t, [])
    assert "service error" in draft_with_key
    assert "NVIDIA" in draft_with_key


def test_degraded_draft_uses_employee_name(monkeypatch):
    from app.models import User

    t = Ticket(title="Printer", description="Jam", employee=User(full_name="Priyanshu Pattanaik"))
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    assert generate_degraded_draft(t, []).startswith("Dear Priyanshu Pattanaik,")


def test_grounding_check_rejects_unsupported_claims():
    t = Ticket(title="VPN", description="VPN is unavailable")
    chunk = type("Doc", (), {"page_content": "VPN setup requires the company VPN client.", "metadata": {}})()
    assert is_supported_reply("Use the company VPN client.", t, [chunk]) is True
    assert is_supported_reply("Your account has been permanently deleted.", t, [chunk]) is False


def test_chat_completion_status_400_fallback(monkeypatch):
    calls = []

    class DummyAPIError(Exception):
        def __init__(self, status_code):
            self.status_code = status_code

    class DummyCompletions:
        def create(self, model, messages, **kwargs):
            calls.append(model)
            if model != DEFAULT_MODEL:
                raise DummyAPIError(400)
            return type("Choice", (), {"choices": [type("Msg", (), {"message": type("Content", (), {"content": "Fallback 400 OK"})()})()]})()

    from app.services import llm
    monkeypatch.setattr(llm.client, "chat", type("Chat", (), {"completions": DummyCompletions()})())
    monkeypatch.setattr(settings, "nvidia_model", "some-invalid-model")

    result = _chat_completion([{"role": "user", "content": "Hi"}])
    assert result == "Fallback 400 OK"
    assert calls == ["some-invalid-model", DEFAULT_MODEL]


def test_rag_retrieval_failure_falls_back(monkeypatch):
    from app.services import rag
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)

    class BrokenRetriever:
        def invoke(self, query):
            raise RuntimeError("Chroma index corrupted or collection deleted")

    class BrokenStore:
        def as_retriever(self, **kwargs):
            return BrokenRetriever()

    monkeypatch.setattr(rag, "_store", BrokenStore())
    t = Ticket(title="VPN", description="Help with VPN connection")
    chunks = rag.get_relevant_chunks(t)
    assert rag._store is None
    assert isinstance(chunks, list)
