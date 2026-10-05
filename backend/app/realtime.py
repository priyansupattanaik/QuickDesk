import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Connection:
    queue: asyncio.Queue[dict[str, Any]]
    user_id: str
    role: str


_connections: set[Connection] = set()


async def register(user_id: str, role: str) -> Connection:
    connection = Connection(asyncio.Queue(maxsize=50), user_id, role)
    _connections.add(connection)
    return connection


async def deregister(connection: Connection) -> None:
    _connections.discard(connection)


async def publish(channel: str, event: str, data: dict[str, Any]) -> None:
    for connection in tuple(_connections):
        if channel == "agents":
            if connection.role != "agent":
                continue
        elif channel != f"user:{connection.user_id}":
            continue
        try:
            connection.queue.put_nowait({"event": event, "data": data})
        except asyncio.QueueFull:
            _connections.discard(connection)
