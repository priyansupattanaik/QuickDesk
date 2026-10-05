import logging
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID

from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select

from app.database import SessionLocal
from app.models import KBArticle, Ticket

logger = logging.getLogger(__name__)
_store: Chroma | None = None
_documents: list[Document] = []
_index_attempted = False
_collection_name = "quickdesk_kb"
_dense_relevance_threshold = 0.2
_minimum_lexical_overlap = 2
_persist_directory = Path(__file__).resolve().parents[2] / "chroma_db"
_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
_stop_words = {
    "the", "and", "for", "with", "that", "this", "from", "your", "have", "will", "need", "into", "are", "not", "our",
    "you", "can", "how", "what", "when", "where", "why", "does", "please", "help", "issue", "problem",
}
_generic_terms = {
    "access", "request", "requests", "requested", "employee", "company", "support", "internal", "portal", "ticket",
}
_token_pattern = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [token for token in _token_pattern.findall(text.lower()) if len(token) >= 3 and token not in _stop_words]


def _content_terms(text: str) -> set[str]:
    return {token for token in _tokens(text) if token not in _generic_terms}


def _build_documents(articles: list[KBArticle]) -> list[Document]:
    documents: list[Document] = []
    for article in articles:
        for chunk_index, chunk in enumerate(_splitter.split_text(article.content)):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "article_id": str(article.id),
                        "title": article.title,
                        "slug": article.slug,
                        "chunk_index": chunk_index,
                    },
                )
            )
    return documents


def rebuild_index() -> None:
    global _store, _documents, _index_attempted
    _index_attempted = True
    try:
        with SessionLocal() as db:
            articles = db.scalars(select(KBArticle).order_by(KBArticle.slug)).all()
        _documents = _build_documents(articles)
        if not _documents:
            _store = None
            return

        try:
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"local_files_only": True},
            )
        except Exception:
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        try:
            existing = Chroma(
                collection_name=_collection_name,
                embedding_function=embeddings,
                persist_directory=str(_persist_directory),
                collection_metadata={"hnsw:space": "cosine"},
                relevance_score_fn=lambda distance: max(0.0, 1.0 - distance),
            )
            existing.delete_collection()
        except Exception:
            pass

        _store = Chroma.from_documents(
            _documents,
            embeddings,
            collection_name=_collection_name,
            persist_directory=str(_persist_directory),
            collection_metadata={"hnsw:space": "cosine"},
            relevance_score_fn=lambda distance: max(0.0, 1.0 - distance),
        )
    except Exception as exc:
        _store = None
        logger.warning("Knowledge base embeddings unavailable; using lexical retrieval fallback: %s", exc)


def _lexical_scores(query: str, documents: list[Document]) -> dict[str, float]:
    query_terms = Counter(_tokens(query))
    if not query_terms or not documents:
        return {}
    document_terms = [_tokens(document.page_content) for document in documents]
    document_frequency = Counter(term for terms in document_terms for term in set(terms))
    scores: dict[str, float] = {}
    for index, terms in enumerate(document_terms):
        term_counts = Counter(terms)
        score = 0.0
        for term, query_count in query_terms.items():
            if term not in term_counts:
                continue
            idf = math.log((1 + len(documents)) / (1 + document_frequency[term])) + 1
            score += (1 + math.log(term_counts[term])) * query_count * idf
        title_terms = set(_tokens(documents[index].metadata.get("title", "")))
        score += 1.5 * len(set(query_terms) & title_terms)
        if score:
            scores[str(index)] = score
    return scores


def _hybrid_candidates(ticket: Ticket) -> list[Document]:
    global _store
    query = f"{ticket.title}\n{ticket.description}"
    lexical_scores = _lexical_scores(query, _documents)
    query_terms = _content_terms(query)
    lexical_ranked = [
        index
        for index in sorted(lexical_scores, key=lexical_scores.get, reverse=True)
        if len(query_terms & _content_terms(_documents[int(index)].page_content)) >= _minimum_lexical_overlap
    ][:8]
    dense_ranked: list[tuple[Document, float]] = []
    if _store is not None:
        try:
            dense_ranked = [
                (document, score)
                for document, score in _store.similarity_search_with_relevance_scores(query, k=8)
                if score >= _dense_relevance_threshold
            ]
        except Exception as exc:
            logger.warning("Dense retrieval failed; using lexical evidence: %s", exc)
            _store = None

    by_key = {str(index): document for index, document in enumerate(_documents)}
    lexical_keys = set(lexical_ranked)
    fused: dict[str, float] = defaultdict(float)
    for rank, index in enumerate(lexical_ranked, start=1):
        fused[index] += 1.0 / (60 + rank)
    for rank, (document, dense_score) in enumerate(dense_ranked, start=1):
        for candidate_key, candidate in by_key.items():
            if candidate_key not in lexical_keys:
                continue
            if (
                candidate.metadata.get("article_id") == document.metadata.get("article_id")
                and candidate.metadata.get("chunk_index") == document.metadata.get("chunk_index")
            ):
                fused[candidate_key] += 1.0 / (60 + rank) + max(0.0, dense_score) * 0.05
                break

    ranked = sorted(fused, key=fused.get, reverse=True)
    return [by_key[key] for key in ranked[:3] if key in by_key]


def get_relevant_chunks(ticket: Ticket) -> list[Document]:
    global _index_attempted
    if not _index_attempted:
        rebuild_index()
    candidates = _hybrid_candidates(ticket)
    if candidates:
        return candidates
    return _lexical_fallback(ticket)


def _lexical_fallback(ticket: Ticket) -> list[Document]:
    """Return only exact text from PostgreSQL when dense retrieval is unavailable."""
    documents = _documents
    if not documents:
        with SessionLocal() as db:
            documents = _build_documents(db.scalars(select(KBArticle).order_by(KBArticle.slug)).all())
    scores = _lexical_scores(f"{ticket.title}\n{ticket.description}", documents)
    query_terms = _content_terms(f"{ticket.title}\n{ticket.description}")
    ranked = [
        index
        for index in sorted(scores, key=scores.get, reverse=True)
        if len(query_terms & _content_terms(documents[int(index)].page_content)) >= _minimum_lexical_overlap
    ]
    return [documents[int(index)] for index in ranked[:3]]


def grounded_context(chunks: list[Document]) -> tuple[list[Document], list[dict[str, str]]]:
    """Return full stored articles for chunks that match those articles exactly."""
    citations = citations_for(chunks)
    documents: list[Document] = []
    with SessionLocal() as db:
        for item in citations:
            article = db.get(KBArticle, UUID(item["article_id"]))
            if article is None:
                continue
            documents.append(
                Document(
                    page_content=article.content,
                    metadata={"article_id": item["article_id"], "title": article.title},
                )
            )
    return documents, citations


def citations_for(chunks: list[Document]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[str] = set()
    with SessionLocal() as db:
        for chunk in chunks:
            article_id = chunk.metadata.get("article_id")
            if not article_id or article_id in seen:
                continue
            try:
                article = db.get(KBArticle, UUID(article_id))
            except ValueError:
                article = None
            if article is None or chunk.page_content.strip() not in article.content:
                logger.warning("Skipping citation that does not match the stored KB article: %s", article_id)
                continue
            seen.add(article_id)
            citations.append(
                {
                    "article_id": article_id,
                    "title": article.title,
                    "snippet": chunk.page_content.strip(),
                    "url": f"/kb/{article_id}",
                }
            )
    return citations
