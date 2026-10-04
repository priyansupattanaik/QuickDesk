import logging
import sys

from app.models import Ticket, User
from app.config import settings

logger = logging.getLogger(__name__)


def build_resolution_email(ticket: Ticket, agent: User) -> dict[str, str]:
    first_name = ticket.employee.full_name.split()[0]
    body = (
        f"Hi {first_name},\n\n"
        f"Your helpdesk ticket \"{ticket.title}\" has been resolved.\n\n"
        f"{ticket.final_reply}\n\n"
        f"Regards,\n{agent.full_name}\nQuickDesk Support"
    )
    return {
        "to": ticket.employee.email,
        "subject": f"[QuickDesk] Resolved: {ticket.title}",
        "body": body,
    }


def notify_resolution(ticket: Ticket, agent: User) -> dict[str, str]:
    if settings.email_backend != "console":
        raise RuntimeError(f"Unsupported email backend: {settings.email_backend}")
    email = build_resolution_email(ticket, agent)
    print(
        f"\n---------- MOCK EMAIL ----------\nTo: {email['to']}\nSubject: {email['subject']}\n{email['body']}\n---------------------------------",
        file=sys.stdout,
        flush=True
    )
    return email
