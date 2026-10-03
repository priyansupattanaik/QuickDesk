import json
import logging
import re
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.nvidia_api_key or "missing", base_url=settings.nvidia_base_url)

CATEGORIES = {"IT", "HR", "Finance", "Admin", "Other"}
PRIORITIES = {"Low", "Medium", "High"}


def _json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or value.get("category") not in CATEGORIES or value.get("priority") not in PRIORITIES:
        return None
    return {"category": value["category"], "priority": value["priority"], "fallback": False}


def classify_ticket(title: str, description: str) -> dict[str, Any]:
    if not settings.nvidia_api_key:
        return {"category": "Other", "priority": "Medium", "fallback": True}
    system = "Return only JSON: {\"category\": one of IT|HR|Finance|Admin|Other, \"priority\": one of Low|Medium|High}."
    user = f"Ticket title: {title}\nTicket description: {description}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for attempt in range(2):
        if attempt:
            messages.append({"role": "user", "content": "Your last response was invalid. Respond with only the JSON object."})
        response = client.chat.completions.create(model=settings.nvidia_model, messages=messages, temperature=0, timeout=15)
        result = _json_object(response.choices[0].message.content or "")
        if result:
            return result
    return {"category": "Other", "priority": "Medium", "fallback": True}


def generate_degraded_draft(ticket: Any, context_chunks: list[Any]) -> str:
    lines = [
        f"Thank you for contacting support regarding \"{ticket.title}\".",
        "",
        "We are reviewing your request:",
        ticket.description.strip(),
        "",
    ]
    if context_chunks:
        lines.append("Relevant knowledge base excerpts:")
        for index, chunk in enumerate(context_chunks, start=1):
            title = chunk.metadata.get("title") if hasattr(chunk, "metadata") else ""
            prefix = f"{index}. {title}: " if title else f"{index}. "
            lines.append(prefix + chunk.page_content.strip())
        lines.append("")
        lines.append("An agent will follow up with the steps above or request more details if needed.")
    else:
        lines.append(
            "We do not have a matching knowledge base article for this issue yet. "
            "An agent will gather more details and follow up shortly."
        )
    lines.append("")
    lines.append("(Draft generated without the NVIDIA NIM provider — configure NVIDIA_API_KEY for AI-written replies.)")
    return "\n".join(lines)


def generate_reply(ticket: Any, context_chunks: list[Any]) -> str:
    if not settings.nvidia_api_key:
        raise RuntimeError("NVIDIA_API_KEY is not configured")
    excerpts = "\n\n".join(chunk.page_content for chunk in context_chunks)
    context = excerpts or "No relevant knowledge base excerpts were found."
    system = (
        "You are drafting a reply for a support agent at an internal helpdesk. "
        "Use ONLY the provided knowledge base excerpts. If no excerpt is relevant to the ticket, "
        "say exactly that you don't have a specific article for this issue and suggest the agent "
        "gather more details — do NOT invent policy. Tone: professional, concise, numbered steps "
        "where applicable, no fluff, no apologies theater, no markdown headers. Do not mention that you are an AI."
    )
    user = f"Ticket title: {ticket.title}\nTicket description: {ticket.description}\n\nKnowledge base excerpts:\n{context}"
    response = client.chat.completions.create(
        model=settings.nvidia_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        timeout=30,
    )
    return (response.choices[0].message.content or "").strip()
