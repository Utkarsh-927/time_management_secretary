from datetime import date, time

from sqlalchemy import Column, Date, Integer, String, Time, Text

from ..database.database import Base


class Availability(Base):
    __tablename__ = "availability"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    start_date = Column(
        Date,
        nullable=False
    )

    end_date = Column(
        Date,
        nullable=False
    )

    start_time = Column(
        Time,
        nullable=False
    )

    end_time = Column(
        Time,
        nullable=False
    )

    recurrence = Column(
        String(50),
        default="none",
        nullable=False
    )

    weekdays = Column(
        Text,
        nullable=True
    )