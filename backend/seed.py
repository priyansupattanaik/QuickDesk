from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from sqlalchemy import select
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import KBArticle, User, UserRole


def seed_user(db, email: str, password: str, full_name: str, role: UserRole) -> None:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        print(f"Skipped {email}")
        return
    db.add(User(email=email, password_hash=hash_password(password), full_name=full_name, role=role))
    db.commit()
    print(f"Created {email}")


def seed_article(db, path: Path) -> None:
    slug = path.stem
    raw_markdown = path.read_text(encoding="utf-8").strip()
    title, _, _ = raw_markdown.partition("\n")
    title = title.removeprefix("# ").strip()
    article = db.scalar(select(KBArticle).where(KBArticle.slug == slug))
    if article is not None:
        article.title = title
        article.content = raw_markdown
        db.commit()
        print(f"Skipped {slug}")
        return
    db.add(KBArticle(slug=slug, title=title, content=raw_markdown))
    db.commit()
    print(f"Created {slug}")


Base.metadata.create_all(engine)
with SessionLocal() as session:
    seed_user(session, "agent@quickdesk.dev", "Agent#Pass1", "Demo Agent", UserRole.agent)
    seed_user(session, "employee@quickdesk.dev", "Employee#Pass1", "Demo Employee", UserRole.employee)
    for article_path in sorted((Path(__file__).parent / "kb").glob("*.md")):
        seed_article(session, article_path)
