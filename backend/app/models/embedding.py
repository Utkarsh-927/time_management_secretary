from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from ..database.database import Base
from ..database.vector import EMBEDDING_DIMENSIONS, VectorType

class Embedding(Base):
    __tablename__ = "embeddings"
    id = Column(Integer, primary_key=True, index=True)
    memory_id = Column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    dimensions = Column(Integer, nullable=False, default=EMBEDDING_DIMENSIONS)
    embedding = Column(VectorType(EMBEDDING_DIMENSIONS), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    source_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("memory_id", "model_name", name="uq_embedding_memory_model"),)
