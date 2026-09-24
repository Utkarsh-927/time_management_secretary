from datetime import datetime
from sqlalchemy import Column, Date, DateTime, Integer, String, Time, Text, Index
from ..database.database import Base
class Availability(Base):
    __tablename__ = "availability"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, default="default", index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    recurrence = Column(String(50), default="none", nullable=False)
    weekdays = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (Index("ix_availability_user_dates", "user_id", "start_date", "end_date"),)
