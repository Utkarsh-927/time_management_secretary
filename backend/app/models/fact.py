from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from ..database.database import Base
JsonType = JSON().with_variant(JSONB(), "postgresql")

class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(120), nullable=False, index=True)
    value_type = Column(String(30), nullable=False, default="text")
    value_text = Column(Text, nullable=True)
    value_number = Column(Float, nullable=True)
    value_datetime = Column(DateTime, nullable=True)
    value_boolean = Column(Boolean, nullable=True)
    value_json = Column(JsonType, nullable=True)
    unit = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    source_note_id = Column(Integer, ForeignKey("raw_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_facts_user_entity_key", "user_id", "entity_id", "key"),
        Index("ix_facts_user_current", "user_id", "is_current"),
    )
