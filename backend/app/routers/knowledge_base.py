from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models import KBArticle, User
from app.schemas import KBArticleResponse


router = APIRouter(prefix="/api/kb", tags=["knowledge base"])


@router.get("/articles/{article_id}", response_model=KBArticleResponse)
def get_article(article_id: UUID, _user: User = Depends(require_role("agent")), db: Session = Depends(get_db)) -> KBArticle:
    article = db.get(KBArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Knowledge-base article not found")
    return article
