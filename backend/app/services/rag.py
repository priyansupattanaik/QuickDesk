import logging
from typing import Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select

from app.database import SessionLocal
from app.models import KBArticle, Ticket

logger = logging.getLogger(__name__)
_store: FAISS | None = None


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
        _store = FAISS.from_documents(documents, embeddings)
    except Exception:
        _store = None
        logger.exception("Knowledge base index could not be built")


def get_relevant_chunks(ticket: Ticket) -> list[Document]:
    if _store is None:
        return []
    return _store.as_retriever(search_kwargs={"k": 3}).invoke(f"{ticket.title}\n{ticket.description}")


def citations_for(chunks: list[Document]) -> list[dict[str, str]]:
    seen: set[str] = set()
    citations = []
    for chunk in chunks:
        article_id = chunk.metadata.get("article_id")
        if article_id and article_id not in seen:
            seen.add(article_id)
            citations.append({"article_id": article_id, "title": chunk.metadata.get("title", "")})
    return citations
