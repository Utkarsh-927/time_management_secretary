from __future__ import annotations

import hashlib
import os

from fastembed import TextEmbedding
from sqlalchemy.orm import Session

from ..models.embedding import Embedding
from ..models.memory import Memory


EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "BAAI/bge-small-en-v1.5",
)

EMBEDDING_DIMENSIONS = 384

_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    global _model

    if _model is None:
        _model = TextEmbedding(EMBEDDING_MODEL_NAME)

    return _model


def generate_embedding(text: str) -> list[float]:
    text = (text or "").strip()

    if not text:
        return []

    model = get_embedding_model()

    vector = next(model.embed([text]))

    return [float(value) for value in vector]


def content_hash(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def create_memory_embedding(
    db: Session,
    memory: Memory,
) -> Embedding | None:

    text = (memory.content or "").strip()

    if not text:
        return None

    existing = (
        db.query(Embedding)
        .filter(
            Embedding.memory_id == memory.id,
            Embedding.model_name == EMBEDDING_MODEL_NAME,
        )
        .first()
    )

    if existing:
        return existing

    vector = generate_embedding(text)

    if not vector:
        return None

    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} dimensions, "
            f"got {len(vector)}"
        )

    embedding = Embedding(
        memory_id=memory.id,
        model_name=EMBEDDING_MODEL_NAME,
        dimensions=len(vector),
        embedding=vector,
        content_hash=content_hash(text),
        source_text=text,
    )

    db.add(embedding)

    return embedding