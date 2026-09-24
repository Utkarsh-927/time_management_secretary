from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index
from ..database.database import Base
class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    reminder_time = Column(DateTime, nullable=True, index=True)
    reminder_type = Column(String(50), default="general")
    related_id = Column(Integer, nullable=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    source_note_id = Column(Integer, ForeignKey("raw_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (Index("ix_reminders_user_time", "user_id", "reminder_time"),)
