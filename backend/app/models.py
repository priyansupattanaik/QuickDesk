import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String, Text, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class UserRole(str, enum.Enum):
    employee = "employee"
    agent = "agent"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.employee, server_default="employee")
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="employee")
    override_logs: Mapped[list["OverrideLog"]] = relationship(back_populates="agent")


class TicketStatus(str, enum.Enum):
    open = "Open"
    resolved = "Resolved"


class KBArticle(Base):
    __tablename__ = "kb_articles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_employee_id", "employee_id"),
        Index("ix_tickets_created_at", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_filename: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus, values_callable=lambda values: [item.value for item in values]), default=TicketStatus.open, server_default="Open", nullable=False)
    ai_category: Mapped[str] = mapped_column(String(20), default="Other", server_default="Other", nullable=False)
    ai_priority: Mapped[str] = mapped_column(String(10), default="Medium", server_default="Medium", nullable=False)
    ai_classified: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    ai_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_draft: Mapped[str | None] = mapped_column(Text)
    ai_citations: Mapped[list[dict] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    final_reply: Mapped[str | None] = mapped_column(Text)
    final_category: Mapped[str | None] = mapped_column(String(20))
    final_priority: Mapped[str | None] = mapped_column(String(10))
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    employee: Mapped[User] = relationship(back_populates="tickets")
    override_logs: Mapped[list["OverrideLog"]] = relationship(back_populates="ticket", order_by="OverrideLog.created_at.desc()", cascade="all, delete-orphan")


class OverrideLog(Base):
    __tablename__ = "override_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(20), nullable=False)
    from_value: Mapped[str] = mapped_column(String(20), nullable=False)
    to_value: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ticket: Mapped[Ticket] = relationship(back_populates="override_logs")
    agent: Mapped[User] = relationship(back_populates="override_logs")
