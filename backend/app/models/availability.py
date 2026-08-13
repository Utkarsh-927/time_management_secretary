from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Time, Text

from ..database.database import Base


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)

    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Daily time window
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)

    # none, daily, weekly
    recurrence = Column(
        String(20),
        default="none",
        nullable=False
    )

    
    # "Monday,Wednesday,Friday"
    weekdays = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )