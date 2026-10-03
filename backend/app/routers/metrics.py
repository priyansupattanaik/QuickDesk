from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models import Ticket, TicketStatus, User

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
def metrics(user: User = Depends(require_role("agent")), db: Session = Depends(get_db)) -> dict:
    status_rows = db.execute(select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)).all()
    by_status = {TicketStatus.open.value: 0, TicketStatus.resolved.value: 0}
    for ticket_status, count in status_rows:
        by_status[ticket_status.value] = count

    category_rows = db.execute(
        select(func.coalesce(Ticket.final_category, Ticket.ai_category).label("category"), func.count(Ticket.id).label("count"))
        .group_by(func.coalesce(Ticket.final_category, Ticket.ai_category))
        .order_by(func.count(Ticket.id).desc())
    ).all()
    by_category = [{"category": category, "count": count} for category, count in category_rows]

    if db.bind.dialect.name == "postgresql":
        median = db.scalar(select(func.percentile_cont(0.5).within_group(func.extract("epoch", Ticket.resolved_at - Ticket.created_at))).where(Ticket.resolved_at.is_not(None)))
    else:
        median = db.scalar(text("""
            WITH durations AS (
                SELECT (julianday(resolved_at) - julianday(created_at)) * 86400.0 AS seconds
                FROM tickets
                WHERE resolved_at IS NOT NULL
            ), ranked AS (
                SELECT seconds, row_number() OVER (ORDER BY seconds) AS row_number, count(*) OVER () AS total
                FROM durations
            )
            SELECT avg(seconds) FROM ranked
            WHERE row_number IN ((total + 1) / 2, (total + 2) / 2)
        """))

    total, overrides = db.execute(select(func.count(Ticket.id), func.count(Ticket.id).filter(Ticket.final_category.is_distinct_from(Ticket.ai_category)))).one()
    override_rate = (100.0 * overrides / total) if total else None
    return {"by_status": by_status, "by_category": by_category, "median_resolution_seconds": float(median) if median is not None else None, "override_rate_percent": override_rate}
