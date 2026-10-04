import logging
import re
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select

from app.database import SessionLocal
from app.models import KBArticle, Ticket

logger = logging.getLogger(__name__)
_store: Chroma | None = None
_collection_name = "quickdesk_kb"
_persist_directory = Path(__file__).resolve().parents[2] / "chroma_db"
_stop_words = {"the", "and", "for", "with", "that", "this", "from", "your", "have", "will", "need", "into", "are", "not", "our"}


def rebuild_index() -> None:
    global _store
    try:
        with SessionLocal() as db:
            articles = db.scalars(select(KBArticle).order_by(KBArticle.slug)).all()
        if not articles:
            _store = None
            return
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        documents = []
        for article in articles:
            for chunk in splitter.split_text(article.content):
                documents.append(Document(page_content=chunk, metadata={"article_id": str(article.id), "title": article.title}))
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={"local_files_only": True})
        existing = Chroma(collection_name=_collection_name, embedding_function=embeddings, persist_directory=str(_persist_directory))
        existing.delete_collection()
        _store = Chroma.from_documents(
            documents,
            embeddings,
            collection_name=_collection_name,
            persist_directory=str(_persist_directory),
        )
    except Exception as exc:
        _store = None
        logger.warning("Knowledge base embeddings unavailable; using lexical retrieval fallback: %s", exc)


def get_relevant_chunks(ticket: Ticket) -> list[Document]:
    global _store
    if _store is None:
        rebuild_index()
    if _store is None:
        return _lexical_fallback(ticket)
    retriever = _store.as_retriever(search_type="similarity_score_threshold", search_kwargs={"k": 3, "score_threshold": 0.2})
    return retriever.invoke(f"{ticket.title}\n{ticket.description}")


def _lexical_fallback(ticket: Ticket) -> list[Document]:
    """Use grounded article text when the optional local embedding model is unavailable."""
    query_terms = {
        term for term in re.findall(r"[a-z0-9]+", f"{ticket.title} {ticket.description}".lower())
        if len(term) >= 3 and term not in _stop_words
    }
    if not query_terms:
        return []
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    ranked: list[tuple[int, Document]] = []
    with SessionLocal() as db:
        articles = db.scalars(select(KBArticle).order_by(KBArticle.slug)).all()
        for article in articles:
            for chunk in splitter.split_text(article.content):
                terms = set(re.findall(r"[a-z0-9]+", chunk.lower()))
                score = len(query_terms & terms)
                if score:
                    ranked.append((score, Document(page_content=chunk, metadata={"article_id": str(article.id), "title": article.title})))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [document for _score, document in ranked[:3]]


def citations_for(chunks: list[Document]) -> list[dict[str, str]]:
    seen: set[str] = set()
    citations = []
    for chunk in chunks:
        article_id = chunk.metadata.get("article_id")
        if article_id and article_id not in seen:
            seen.add(article_id)
            citations.append({"article_id": article_id, "title": chunk.metadata.get("title", "")})
    return citations
