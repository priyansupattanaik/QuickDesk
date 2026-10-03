from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from sqlalchemy import select
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole


def seed_user(db, email: str, password: str, full_name: str, role: UserRole) -> None:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        print(f"Skipped {email}")
        return
    db.add(User(email=email, password_hash=hash_password(password), full_name=full_name, role=role))
    db.commit()
    print(f"Created {email}")


Base.metadata.create_all(engine)
with SessionLocal() as session:
    seed_user(session, "agent@quickdesk.dev", "Agent#Pass1", "Demo Agent", UserRole.agent)
    seed_user(session, "employee@quickdesk.dev", "Employee#Pass1", "Demo Employee", UserRole.employee)

