import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./data/management_model.db",
)


# Ensure the SQLite database directory exists.
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    db_file = Path(db_path)

    if str(db_file.parent) != ".":
        db_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()