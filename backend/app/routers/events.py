import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import ALLOWED_ORIGINS
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User
from app.realtime import deregister, register

router = APIRouter(prefix="/api", tags=["events"])


def _user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        user = db.get(User, UUID(user_id)) if user_id else None
    except (jwt.PyJWTError, ValueError, TypeError):
        user = None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


@router.get("/events")
async def events(request: Request, token: str | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = _user_from_token(token, db)
    connection = await register(str(user.id), user.role.value)

    async def stream() -> AsyncIterator[str]:
        try:
            yield ": heartbeat\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(connection.queue.get(), timeout=25)
                    yield f"event: {message['event']}\ndata: {json.dumps(message['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            await deregister(connection)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)
