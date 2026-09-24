import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def _normalize_database_url(url: str) -> str:
    """Normalize hosted PostgreSQL URLs for SQLAlchemy + psycopg 3."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


# PostgreSQL + pgvector is the target database. SQLite remains a convenient
# fallback for unit tests and offline development when DATABASE_URL is absent.
DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./data/management_model.db")
)

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

if IS_SQLITE:
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    db_file = Path(db_path)
    if str(db_file.parent) != ".":
        db_file.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
