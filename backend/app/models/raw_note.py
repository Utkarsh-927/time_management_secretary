from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Index
from ..database.database import Base

class RawNote(Base):
    __tablename__ = "raw_notes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    raw_text = Column(Text, nullable=False)
    source = Column(String(50), nullable=False, default="chat")
    conversation_id = Column(Integer, ForeignKey("conversation_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    processed = Column(Boolean, nullable=False, default=False, index=True)
    processing_status = Column(String(30), nullable=False, default="pending")
    processing_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    __table_args__ = (Index("ix_raw_notes_user_created", "user_id", "created_at"),)
