from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .connection import Base


class TaskDB(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    deadline: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    estimated_duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    importance: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class MeetingDB(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    start_time: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    end_time: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    participants: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class AvailabilityDB(Base):
    __tablename__ = "availability"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    start_date: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    end_date: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    start_time: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    end_time: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    recurrence: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    weekdays: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class ReminderDB(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    reminder_time: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    reminder_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )