from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models import OverrideLog


with engine.begin() as connection:
    inspector = inspect(connection)
    if not inspector.has_table("tickets"):
        Base.metadata.create_all(connection)
    else:
        columns = {column["name"] for column in inspector.get_columns("tickets")}
        for name, sql_type in (("final_category", "VARCHAR(20)"), ("final_priority", "VARCHAR(10)"), ("ai_confidence", "INTEGER")):
            if name not in columns:
                connection.execute(text(f"ALTER TABLE tickets ADD COLUMN {name} {sql_type}"))
        connection.execute(text("UPDATE tickets SET final_category = ai_category WHERE final_category IS NULL"))
        connection.execute(text("UPDATE tickets SET final_priority = ai_priority WHERE final_priority IS NULL"))
        OverrideLog.__table__.create(connection, checkfirst=True)

print("Migration complete")
