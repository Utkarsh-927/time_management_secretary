from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from ..database.database import Base
JsonType = JSON().with_variant(JSONB(), "postgresql")

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    title = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="active", index=True)
    metadata_json = Column("metadata", JsonType, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column("metadata", JsonType, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)
