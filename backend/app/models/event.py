from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from ..database.database import Base
JsonType = JSON().with_variant(JSONB(), "postgresql")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    event_type = Column(String(80), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_time = Column(DateTime, nullable=True, index=True)
    end_time = Column(DateTime, nullable=True)
    primary_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    source_note_id = Column(Integer, ForeignKey("raw_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    metadata_json = Column("metadata", JsonType, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_events_user_time", "user_id", "event_time"),)
