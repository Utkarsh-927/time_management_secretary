from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ..database.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)

    description = Column(Text, nullable=True)

    deadline = Column(DateTime, nullable=True)

    estimated_duration = Column(Integer, nullable=True)

    importance = Column(Integer, default=3)

    priority_score = Column(Integer, default=0)

    status = Column(String(50), default="pending")

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )