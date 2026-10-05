"""Ticket classification and RAG-grounded reply drafts via Groq."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

CATEGORIES = {"IT", "HR", "Finance", "Admin", "Other"}
PRIORITIES = {"Low", "Medium", "High"}

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_CATEGORY_TERMS = {
    "IT": (
        "vpn",
        "password",
        "login",
        "laptop",
        "hardware",
        "email",
        "drive",
        "account",
        "lockout",
        "wifi",
        "software",
        "computer",
    ),
    "HR": ("leave", "vacation", "pto", "holiday", "absence", "sick"),
    "Finance": ("expense", "reimbursement", "invoice", "receipt", "payroll"),
    "Admin": ("badge", "printer", "facilities", "office", "lobby"),
}
_HIGH_TERMS = ("urgent", "production", "outage", "locked", "lockout", "cannot", "blocked", "down", "asap")
_LOW_TERMS = ("question", "wondering", "whenever", "not urgent", "low priority")


class DraftGenerationError(RuntimeError):
    """Raised when a grounded AI draft cannot be produced."""


def _text(title: str, description: str) -> str:
    return f"{title} {description}".lower()


def _keyword_classify(title: str, description: str) -> dict[str, Any]:
    text = _text(title, description)
    scores = {category: sum(term in text for term in terms) for category, terms in _CATEGORY_TERMS.items()}
    best_category, hits = max(scores.items(), key=lambda item: item[1])
    if hits == 0 or best_category not in CATEGORIES:
        return {"category": "Other", "priority": "Medium", "confidence": None, "fallback": True}

    if any(term in text for term in _HIGH_TERMS):
        priority = "High"
    elif any(term in text for term in _LOW_TERMS):
        priority = "Low"
    else:
        priority = "Medium"
    confidence = min(100, 40 + hits * 15)
    return {"category": best_category, "priority": priority, "confidence": confidence, "fallback": False}


def _require_groq_key() -> str:
    key = (settings.groq_api_key or "").strip()
    if not key:
        raise DraftGenerationError("GROQ_API_KEY is not set. No draft was saved.")
    return key


def _chat(system: str, user: str, *, temperature: float, response_format: dict[str, str] | None = None) -> str:
    key = _require_groq_key()
    model = (settings.groq_model or "qwen/qwen3.8-27b").strip()
    body: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "top_p": 0.8,
        "max_tokens": 500,
        "reasoning_effort": "none",
        "reasoning_format": "hidden",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if response_format is not None:
        body["response_format"] = response_format
    request = urllib.request.Request(
        f"{_GROQ_BASE_URL}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "QuickDesk/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        logger.warning("Groq HTTP %s: %s", exc.code, detail)
        raise DraftGenerationError("Groq could not generate a draft. No draft was saved.") from exc
    except Exception as exc:
        logger.exception("Groq request failed")
        raise DraftGenerationError("Groq could not generate a draft. No draft was saved.") from exc
    content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    content = _visible_reply(content)
    if not content:
        raise DraftGenerationError("Groq returned an empty draft. No draft was saved.")
    return content


def _visible_reply(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def _chat_json(system: str, user: str) -> dict[str, Any]:
    content = _chat(system, user, temperature=0, response_format={"type": "json_object"})
    return json.loads(content)


def _chat_text(system: str, user: str, *, temperature: float = 0.4) -> str:
    return _chat(system, user, temperature=temperature)


def _normalize_classification(payload: dict[str, Any]) -> dict[str, Any] | None:
    category = str(payload.get("category", "")).strip()
    priority = str(payload.get("priority", "")).strip()
    if category not in CATEGORIES or priority not in PRIORITIES:
        return None
    confidence_raw = payload.get("confidence")
    confidence: int | None
    try:
        confidence = int(confidence_raw) if confidence_raw is not None else None
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None:
        confidence = max(0, min(100, confidence))
    return {
        "category": category,
        "priority": priority,
        "confidence": confidence,
        "fallback": False,
    }


def classify_ticket(title: str, description: str) -> dict[str, Any]:
    """Classify with Groq when configured; otherwise use local keyword rules."""
    if not (settings.groq_api_key or "").strip():
        return _keyword_classify(title, description)

    system = (
        "You classify internal helpdesk tickets. "
        "Return JSON only with keys category, priority, confidence. "
        f"category must be one of: {', '.join(sorted(CATEGORIES))}. "
        f"priority must be one of: {', '.join(sorted(PRIORITIES))}. "
        "confidence is an integer 0-100. "
        "If the request is unclear, use category Other, priority Medium, and a low confidence."
    )
    user = f"Title: {title}\n\nDescription: {description}"
    try:
        payload = _chat_json(system, user)
        normalized = _normalize_classification(payload)
        if normalized is not None:
            return normalized
        logger.warning("Groq classification returned invalid labels; using keyword fallback")
    except Exception as exc:
        logger.warning("Groq classification failed; using keyword fallback: %s", exc)
    return _keyword_classify(title, description)


def _format_excerpts(context_chunks: list[Any]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(context_chunks, start=1):
        title = getattr(chunk, "metadata", {}) or {}
        article_title = title.get("title") if isinstance(title, dict) else None
        body = " ".join(getattr(chunk, "page_content", "").split())
        if not body:
            continue
        heading = article_title or f"Excerpt {index}"
        blocks.append(f"[{index}] {heading}\n{body}")
    return "\n\n".join(blocks)


_URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")


def _reject_ungrounded(draft: str, excerpts: str) -> str:
    source = excerpts.lower()
    for url in _URL_PATTERN.findall(draft):
        if url.rstrip(".,);").lower() not in source:
            raise DraftGenerationError("The draft included a link that is not in the knowledge base. No draft was saved.")
    return draft


def _clean_reply(draft: str, team_name: str) -> str:
    """Clean unwanted prefixes/markdown headings and fix any placeholder artifacts."""
    cleaned = re.sub(r"^(?:Subject|Re|Fwd):\s*[^\n]*\n+", "", draft, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(
        r"\[(?:Your Name|Agent Name|Support Agent|Your Title|Insert Name|Name)\]",
        team_name,
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def generate_reply(ticket: Any, context_chunks: list[Any]) -> str:
    """Draft a well-formatted, grounded reply with Groq using only validated knowledge-base excerpts."""
    _require_groq_key()
    employee_name = getattr(getattr(ticket, "employee", None), "full_name", None) or "there"
    title = (getattr(ticket, "title", None) or "").strip()
    description = (getattr(ticket, "description", None) or "").strip()
    category = getattr(ticket, "final_category", None) or getattr(ticket, "ai_category", None) or "Support"
    team_name = f"{category} Support Team" if category in {"IT", "HR", "Finance", "Admin"} else "QuickDesk Support Team"

    excerpts = _format_excerpts(context_chunks)
    retrieved = excerpts or "No knowledge-base articles were retrieved for this ticket."

    system = (
        "You are an experienced, helpful internal helpdesk support agent drafting a direct reply to an employee. "
        "Your draft will be sent directly to the employee, so format it cleanly like an actual professional ticket reply.\n\n"
        "Formatting Guidelines:\n"
        f"1. Salutation: Start with a personalized greeting on its own line (e.g., 'Hi {employee_name},' or 'Hello {employee_name},'), followed by a blank line.\n"
        "2. Structure: Break your reply into clear, readable paragraphs and sections separated by blank lines. Never output a single dense block or wall of text.\n"
        "3. Step-by-Step Instructions: When providing procedures or instructions from the excerpts, format them as a clean numbered list (1., 2., 3., etc.).\n"
        "4. Bullet Points: Use clear bullet points (- item) for options, prerequisites, or lists of details.\n"
        "5. Clean Text: Do NOT include email header fields (like 'Subject:'). Do NOT use Markdown heading hashes ('#', '##', '###').\n"
        "6. Next Steps & Assistance: Include a brief helpful closing sentence encouraging them to reach out if they encounter further issues.\n"
        f"7. Sign-off: Conclude with a warm, professional closing followed by the team signature on a new line (e.g., 'Best regards,\n{team_name}'). Never use bracketed placeholder names like '[Your Name]'.\n\n"
        "Grounding & Anti-Hallucination Rules:\n"
        "1. Rely STRICTLY and EXCLUSIVELY on the provided knowledge-base excerpts and ticket details. Do NOT invent policies, URLs, tools, contacts, approvers, or procedures not present in the excerpts.\n"
        "2. If an excerpt provides step-by-step instructions, follow those exact factual steps accurately.\n"
        "3. If no knowledge-base articles were retrieved, say that we do not have any knowledge about this yet and that we will look into it and get back to you. Do not add causes, steps, tools, or links.\n"
        "4. Never reference 'the excerpts', 'knowledge-base article', 'the provided text', or mention that you are an AI or language model."
    )
    user = (
        f"Employee name: {employee_name}\n"
        f"Ticket title: {title}\n"
        f"Ticket description: {description}\n\n"
        f"Knowledge-base retrieval result:\n{retrieved}\n\n"
        "Draft the reply."
    )
    try:
        draft = _chat_text(system, user, temperature=0 if not excerpts else 0.4)
    except DraftGenerationError:
        raise
    except Exception as exc:
        logger.exception("Groq draft generation failed")
        raise DraftGenerationError("Groq could not generate a draft. No draft was saved.") from exc

    draft = _clean_reply(draft, team_name)
    if not draft:
        raise DraftGenerationError("Groq returned an empty draft. No draft was saved.")
    if not excerpts:
        _require_llm_gap_reply(draft)
        return draft
    return _reject_ungrounded(draft, excerpts)


def _require_llm_gap_reply(draft: str) -> None:
    """Reject a no-match reply that was not produced as a plain follow-up, without substituting text."""
    lowered = draft.lower()
    acknowledges = any(
        phrase in lowered
        for phrase in ("do not have", "don't have", "no knowledge", "not have any knowledge", "no documented")
    )
    will_follow_up = "look into" in lowered and "get back" in lowered and "you" in lowered
    invented = bool(_URL_PATTERN.search(draft) or re.search(r"(?m)^\s*\d+\.\s", draft))
    if invented or not acknowledges or not will_follow_up or " to them" in lowered:
        raise DraftGenerationError("The model did not return a grounded follow-up. No draft was saved.")
