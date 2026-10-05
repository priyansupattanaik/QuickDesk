import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.deps import get_current_user, require_role
from app.database import get_db
from app.models import OverrideLog, Ticket, TicketStatus, User
from app.schemas import ClassificationOverride, TicketCreate, TicketListResponse, TicketReply, TicketResponse
from app.realtime import publish
from app.services.llm import classify_ticket, generate_degraded_draft, generate_reply
from app.services.notifier import notify_resolution
from app.services.rag import citations_for, get_relevant_chunks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _ticket_query() -> select:
    return select(Ticket).options(joinedload(Ticket.employee), selectinload(Ticket.override_logs).joinedload(OverrideLog.agent))


def _get_ticket(ticket_id: UUID, db: Session) -> Ticket:
    ticket = db.scalar(_ticket_query().where(Ticket.id == ticket_id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: TicketCreate, user: User = Depends(require_role("employee", "agent")), db: Session = Depends(get_db)) -> Ticket:
    ticket = Ticket(employee_id=user.id, title=payload.title, description=payload.description, attachment_filename=payload.attachment_filename)
    db.add(ticket)
    db.flush()
    try:
        result = classify_ticket(ticket.title, ticket.description)
        ticket.ai_category = result["category"]
        ticket.ai_priority = result["priority"]
        ticket.ai_confidence = result.get("confidence")
        ticket.final_category = result["category"]
        ticket.final_priority = result["priority"]
        ticket.ai_classified = not result.get("fallback", False)
    except Exception:
        logger.exception("Ticket classification failed")
        ticket.ai_category = "Other"
        ticket.ai_priority = "Medium"
        ticket.final_category = "Other"
        ticket.final_priority = "Medium"
        ticket.ai_classified = False
    db.commit()
    created = _get_ticket(ticket.id, db)
    await publish("agents", "ticket_created", {"id": str(created.id), "title": created.title, "ai_category": created.ai_category, "ai_priority": created.ai_priority, "status": created.status.value, "created_at": created.created_at.isoformat(), "employee_email": created.employee.email})
    return created


@router.get("/mine", response_model=list[TicketResponse])
def mine(status_filter: TicketStatus | None = Query(default=None, alias="status"), user: User = Depends(require_role("employee", "agent")), db: Session = Depends(get_db)) -> list[Ticket]:
    query = _ticket_query().where(Ticket.employee_id == user.id).order_by(Ticket.created_at.desc())
    if status_filter:
        query = query.where(Ticket.status == status_filter)
    return list(db.scalars(query).unique().all())


@router.get("", response_model=TicketListResponse)
def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None, max_length=20),
    priority: str | None = Query(default=None, max_length=10),
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_role("agent")),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Ticket).options(joinedload(Ticket.employee), selectinload(Ticket.override_logs).joinedload(OverrideLog.agent))
    filters = []
    if status_filter:
        filters.append(Ticket.status == status_filter)
    if category:
        filters.append(Ticket.final_category == category)
    if priority:
        filters.append(Ticket.final_priority == priority)
    if q:
        filters.append(Ticket.title.ilike(f"%{_escape_like(q)}%", escape="\\"))
    query = query.where(*filters)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    ticket = _get_ticket(ticket_id, db)
    if user.role.value != "agent" and ticket.employee_id != user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return ticket


@router.patch("/{ticket_id}/classification", response_model=TicketResponse)
def override_classification(ticket_id: UUID, payload: ClassificationOverride, user: User = Depends(require_role("agent")), db: Session = Depends(get_db)) -> Ticket:
    if payload.final_category is None and payload.final_priority is None:
        raise HTTPException(status_code=422, detail="At least one classification value is required")
    ticket = _get_ticket(ticket_id, db)
    if payload.final_category is not None and payload.final_category != (ticket.final_category or ticket.ai_category):
        db.add(OverrideLog(ticket=ticket, agent_id=user.id, field="category", from_value=ticket.final_category or ticket.ai_category, to_value=payload.final_category))
        ticket.final_category = payload.final_category
    if payload.final_priority is not None and payload.final_priority != (ticket.final_priority or ticket.ai_priority):
        db.add(OverrideLog(ticket=ticket, agent_id=user.id, field="priority", from_value=ticket.final_priority or ticket.ai_priority, to_value=payload.final_priority))
        ticket.final_priority = payload.final_priority
    db.commit()
    return _get_ticket(ticket.id, db)


@router.post("/{ticket_id}/ai-draft")
def draft(ticket_id: UUID, user: User = Depends(require_role("agent")), db: Session = Depends(get_db)) -> dict:
    ticket = _get_ticket(ticket_id, db)
    degraded = False
    try:
        chunks = get_relevant_chunks(ticket)
        citations = citations_for(chunks)
        draft_text = generate_reply(ticket, chunks)
    except Exception:
        logger.exception("AI draft generation failed; using degraded template draft")
        try:
            chunks = get_relevant_chunks(ticket)
            citations = citations_for(chunks)
        except Exception:
            chunks = []
            citations = []
        draft_text = generate_degraded_draft(ticket, chunks)
        degraded = True
    ticket.ai_draft = draft_text
    ticket.ai_citations = citations
    db.commit()
    return {"ai_draft": draft_text, "citations": citations, "degraded": degraded}


@router.post("/{ticket_id}/reply", response_model=TicketResponse)
async def reply(ticket_id: UUID, payload: TicketReply, user: User = Depends(require_role("agent")), db: Session = Depends(get_db)) -> Ticket:
    ticket = _get_ticket(ticket_id, db)
    if ticket.status != TicketStatus.open:
        raise HTTPException(status_code=409, detail="Ticket already resolved")
    ticket.final_reply = payload.reply_text
    ticket.status = TicketStatus.resolved
    ticket.resolved_at = datetime.now(timezone.utc)
    db.commit()
    resolved = _get_ticket(ticket.id, db)
    try:
        notify_resolution(resolved, user)
    except Exception:
        # A notification failure must not undo a committed resolution.
        logger.exception("Resolution notification failed")
    await publish(f"user:{resolved.employee_id}", "ticket_resolved", {"ticket_id": str(resolved.id), "status": resolved.status.value, "resolved_at": resolved.resolved_at.isoformat()})
    return resolved
