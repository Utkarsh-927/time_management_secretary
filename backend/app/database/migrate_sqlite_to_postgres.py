"""Optional one-time copy of existing operational data from SQLite to PostgreSQL.

Run only after backing up your SQLite database and initializing PostgreSQL.
Example:
  python -m app.database.migrate_sqlite_to_postgres --sqlite ./data/management_model.db
"""
import argparse
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import Session
from .database import engine, IS_POSTGRES
from .init_db import init_database
from ..models import Task, Meeting, Reminder, Availability

TABLE_MODELS = {
    "tasks": Task,
    "meetings": Meeting,
    "reminders": Reminder,
    "availability": Availability,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True)
    args = parser.parse_args()
    if not IS_POSTGRES:
        raise SystemExit("Target DATABASE_URL must point to PostgreSQL.")

    init_database()
    source_engine = create_engine(f"sqlite:///{args.sqlite}")
    metadata = MetaData()
    target = Session(bind=engine)
    counts = {}
    try:
        for table_name, model in TABLE_MODELS.items():
            source_table = Table(table_name, metadata, autoload_with=source_engine)
            with source_engine.connect() as conn:
                rows = conn.execute(select(source_table)).mappings().all()
            copied = 0
            for row in rows:
                allowed = {c.name for c in model.__table__.columns}
                payload = {k: v for k, v in dict(row).items() if k in allowed}
                payload.pop("id", None)  # let PostgreSQL allocate IDs safely
                target.add(model(**payload))
                copied += 1
            counts[table_name] = copied
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()
    print("Migration complete:", counts)

if __name__ == "__main__":
    main()
