from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.deps import require_role
from app.database import get_db
from app.models import User, UserRole


router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/summary")
def summary(user: User = Depends(require_role("agent")), db: Session = Depends(get_db)) -> dict[str, int | str]:
    total_agents = db.scalar(select(func.count(User.id)).where(User.role == UserRole.agent)) or 0
    return {"total_agents": total_agents, "message": "Agent-only endpoint reachable"}
