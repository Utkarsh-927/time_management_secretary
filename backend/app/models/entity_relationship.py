from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from ..database.database import Base
JsonType = JSON().with_variant(JSONB(), "postgresql")

class EntityRelationship(Base):
    __tablename__ = "entity_relationships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(80), nullable=False, index=True)
    target_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    metadata_json = Column("metadata", JsonType, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    source_note_id = Column(Integer, ForeignKey("raw_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_relationships_user_source", "user_id", "source_entity_id"),
        Index("ix_relationships_user_target", "user_id", "target_entity_id"),
    )
