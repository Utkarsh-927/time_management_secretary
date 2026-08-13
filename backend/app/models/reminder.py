from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ..database.database import Base


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)

    message = Column(Text, nullable=True)

    reminder_time = Column(DateTime, nullable=False)

    # task / meeting / general
    reminder_type = Column(
        String(50),
        default="general"
    )

    # ID of the related task or meeting
    related_id = Column(
        Integer,
        nullable=True
    )

    status = Column(
        String(50),
        default="pending"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )