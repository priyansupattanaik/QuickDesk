import json
import logging
import re
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)
client = OpenAI(api_key=(settings.nvidia_api_key or "").strip() or "missing", base_url=settings.nvidia_base_url)

DEFAULT_MODEL = "meta/llama-3.2-11b-vision-instruct"
DECOMMISSIONED_MODELS = {"meta/llama-3.3-70b-instruct"}
CATEGORIES = {"IT", "HR", "Finance", "Admin", "Other"}
PRIORITIES = {"Low", "Medium", "High"}


def _resolve_model(model_name: str | None = None) -> str:
    chosen = (model_name or settings.nvidia_model or "").strip()
    if chosen in DECOMMISSIONED_MODELS or not chosen:
        return DEFAULT_MODEL
    return chosen


def _chat_completion(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 30) -> str:
    current_key = (settings.nvidia_api_key or "").strip()
    if hasattr(client, "api_key") and current_key and client.api_key != current_key:
        client.api_key = current_key
    model = _resolve_model()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code in (400, 404, 410) and model != DEFAULT_MODEL:
            logger.warning("NVIDIA model %s returned HTTP %s; falling back to %s", model, status_code, DEFAULT_MODEL)
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            return (response.choices[0].message.content or "").strip()
        raise


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
    
    confidence = value.get("confidence")
    if confidence is not None:
        try:
            confidence = int(confidence)
            if not (0 <= confidence <= 100):
                confidence = None
        except (ValueError, TypeError):
            confidence = None

    return {"category": value["category"], "priority": value["priority"], "confidence": confidence, "fallback": False}


def classify_ticket(title: str, description: str) -> dict[str, Any]:
    if not (settings.nvidia_api_key or "").strip():
        return {"category": "Other", "priority": "Medium", "fallback": True}
    system = "Return only JSON: {\"category\": one of IT|HR|Finance|Admin|Other, \"priority\": one of Low|Medium|High, \"confidence\": integer 0-100}."
    user = f"Ticket title: {title}\nTicket description: {description}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for attempt in range(2):
        if attempt:
            messages.append({"role": "user", "content": "Your last response was invalid. Respond with only the JSON object."})
        raw_content = _chat_completion(messages=messages, temperature=0, timeout=15)
        result = _json_object(raw_content)
        if result:
            return result
    return {"category": "Other", "priority": "Medium", "fallback": True}


def generate_degraded_draft(ticket: Any, context_chunks: list[Any]) -> str:
    employee_name = getattr(getattr(ticket, "employee", None), "full_name", None) or "the employee"
    lines = [
        f"Dear {employee_name},",
        "",
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
    if not (settings.nvidia_api_key or "").strip():
        lines.append("(Draft generated without the NVIDIA NIM provider — configure NVIDIA_API_KEY for AI-written replies.)")
    else:
        lines.append("(Draft generated without the NVIDIA NIM provider — upstream service error.)")
    return "\n".join(lines)


def _grounding_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 4}


def is_supported_reply(reply: str, ticket: Any, context_chunks: list[Any]) -> bool:
    """Conservatively reject generated sentences with no evidence in the ticket or KB."""
    if not reply.strip() or not context_chunks:
        return False
    evidence = _grounding_tokens(" ".join(chunk.page_content for chunk in context_chunks))
    employee_name = getattr(getattr(ticket, "employee", None), "full_name", "")
    allowed_personal = _grounding_tokens(employee_name)
    safe_words = {"dear", "thank", "contact", "support", "regarding", "request", "agent", "follow", "shortly", "details"}
    for sentence in re.split(r"(?<=[.!?])\s+", reply.strip()):
        tokens = _grounding_tokens(sentence)
        if not tokens:
            continue
        unsupported = tokens - evidence - allowed_personal - safe_words
        if unsupported:
            return False
    return True


def generate_reply(ticket: Any, context_chunks: list[Any]) -> str:
    if not (settings.nvidia_api_key or "").strip():
        raise RuntimeError("NVIDIA_API_KEY is not configured")
    excerpts = "\n\n".join(chunk.page_content for chunk in context_chunks)
    context = excerpts or "No relevant knowledge base excerpts were found."
    employee_name = getattr(getattr(ticket, "employee", None), "full_name", None) or "the employee"
    system = (
        "You are drafting a professional reply on behalf of an internal IT & HR helpdesk agent to the employee who submitted the ticket. "
        "The draft will be reviewed by the agent and sent directly to the employee. "
        "Strict Grounding: Rely strictly and exclusively on the provided knowledge base excerpts. "
        "Do NOT invent policy, tools, URLs, software, contacts, or procedures not present in the excerpts. "
        "If no excerpt is relevant to the ticket or if the issue is not covered in the excerpts, "
        "state that there is no matching knowledge base article for this issue, ask the requester for any relevant details needed to investigate, "
        "and inform them that an agent will follow up shortly — do NOT invent any steps or policy. "
        "Tone: professional, helpful, concise, numbered steps where applicable, no fluff, no apologies theater, no markdown headers. "
        f"Address the employee by their exact name when greeting them: {employee_name}. "
        "Do not mention that you are an AI or language model."
    )
    user = f"Employee name: {employee_name}\nTicket title: {ticket.title}\nTicket description: {ticket.description}\n\nKnowledge base excerpts:\n{context}"
    response = _chat_completion(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        timeout=30,
    )
    if not is_supported_reply(response, ticket, context_chunks):
        raise ValueError("Generated reply failed the conservative grounding check")
    return response
