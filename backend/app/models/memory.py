from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from ..database.database import Base
JsonType = JSON().with_variant(JSONB(), "postgresql")

class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    memory_type = Column(String(80), nullable=False, default="general", index=True)
    content = Column(Text, nullable=False)
    importance = Column(Float, nullable=False, default=0.5, index=True)
    confidence = Column(Float, nullable=False, default=1.0)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    source_note_id = Column(Integer, ForeignKey("raw_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    metadata_json = Column("metadata", JsonType, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (Index("ix_memories_user_active", "user_id", "is_active"),)
