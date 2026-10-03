import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models import TicketStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    created_at: datetime


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserSummary


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    attachment_filename: str | None = Field(default=None, max_length=255)


class TicketReply(BaseModel):
    reply_text: str = Field(min_length=1, max_length=10000)


class EmployeeSummary(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    description: str
    attachment_filename: str | None
    status: TicketStatus
    ai_category: str
    ai_priority: str
    ai_classified: bool
    ai_draft: str | None
    ai_citations: list[dict] | None
    final_reply: str | None
    employee: EmployeeSummary
    created_at: datetime
    resolved_at: datetime | None


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int
