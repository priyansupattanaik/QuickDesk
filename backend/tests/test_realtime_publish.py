import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_quickdesk.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("QUICKDESK_ENV", "test")

from app.realtime import deregister, publish, register


async def _collect_agents_broadcast(role: str, user_id: str) -> list[dict]:
    connection = await register(user_id, role)
    await publish("agents", "ticket_created", {"id": "t1", "employee_email": "secret@example.com"})
    messages = []
    while not connection.queue.empty():
        messages.append(connection.queue.get_nowait())
    await deregister(connection)
    return messages


def test_agents_channel_skips_employee_connections():
    employee_messages = asyncio.run(_collect_agents_broadcast("employee", "emp-1"))
    agent_messages = asyncio.run(_collect_agents_broadcast("agent", "agent-1"))
    assert employee_messages == []
    assert len(agent_messages) == 1
    assert agent_messages[0]["event"] == "ticket_created"
    assert agent_messages[0]["data"]["employee_email"] == "secret@example.com"


async def _collect_user_event(user_id: str) -> list[dict]:
    connection = await register(user_id, "employee")
    await publish(f"user:{user_id}", "ticket_resolved", {"ticket_id": "t1", "status": "Resolved"})
    messages = []
    while not connection.queue.empty():
        messages.append(connection.queue.get_nowait())
    await deregister(connection)
    return messages


def test_user_channel_does_not_include_employee_email():
    messages = asyncio.run(_collect_user_event("emp-1"))
    assert messages == [{"event": "ticket_resolved", "data": {"ticket_id": "t1", "status": "Resolved"}}]
