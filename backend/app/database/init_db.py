from sqlalchemy import text
from .database import Base, engine, IS_POSTGRES
from .. import models  # noqa: F401 - registers every table with Base


def init_database():
    if IS_POSTGRES:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    if IS_POSTGRES:
        # HNSW cosine index for semantic memory retrieval. The extension must
        # exist before this index is created.
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_embeddings_hnsw_cosine "
                "ON embeddings USING hnsw (embedding vector_cosine_ops)"
            ))


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully.")
