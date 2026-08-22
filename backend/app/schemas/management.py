from typing import Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[str] = None
    estimated_duration: Optional[int] = None
    importance: Optional[int] = Field(
        default=None,
        ge=1,
        le=5
    )


class Meeting(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    participants: Optional[list[str]] = None


class Availability(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurrence: Optional[str] = None
    weekdays: Optional[list[str]] = None


class Reminder(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    reminder_time: Optional[str] = None
    reminder_type: Optional[str] = None


class ManagementData(BaseModel):
    tasks: list[Task] = Field(default_factory=list)
    meetings: list[Meeting] = Field(default_factory=list)
    availability: list[Availability] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)