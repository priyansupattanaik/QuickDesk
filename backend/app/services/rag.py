import logging
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


def rebuild_index() -> None:
    global _store
    with SessionLocal() as db:
        articles = db.scalars(select(KBArticle).order_by(KBArticle.slug)).all()
    if not articles:
        _store = None
        return
    try:
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
    except Exception:
        _store = None
        logger.exception("Knowledge base index could not be built")


def get_relevant_chunks(ticket: Ticket) -> list[Document]:
    global _store
    if _store is None:
        rebuild_index()
    if _store is None:
        return []
    retriever = _store.as_retriever(search_type="similarity_score_threshold", search_kwargs={"k": 3, "score_threshold": 0.2})
    return retriever.invoke(f"{ticket.title}\n{ticket.description}")


def citations_for(chunks: list[Document]) -> list[dict[str, str]]:
    seen: set[str] = set()
    citations = []
    for chunk in chunks:
        article_id = chunk.metadata.get("article_id")
        if article_id and article_id not in seen:
            seen.add(article_id)
            citations.append({"article_id": article_id, "title": chunk.metadata.get("title", "")})
    return citations
