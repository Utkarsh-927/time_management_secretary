from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from ..database.database import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")

class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    canonical_key = Column(String(320), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="active", index=True)
    metadata_json = Column("metadata", JsonType, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_key", name="uq_entities_user_canonical"),
        Index("ix_entities_user_type", "user_id", "entity_type"),
    )
