from typing import List, Optional

from pydantic import BaseModel


class ExtractedTask(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[str] = None
    estimated_duration: Optional[int] = None
    importance: int = 3


class ExtractedMeeting(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: str
    end_time: str
    location: Optional[str] = None
    participants: Optional[str] = None


class ExtractedAvailability(BaseModel):
    start_date: str
    end_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurrence: str = "none"
    weekdays: Optional[str] = None


class ExtractedReminder(BaseModel):
    title: str
    message: Optional[str] = None
    reminder_time: Optional[str] = None
    reminder_type: str = "general"


class ExtractionResult(BaseModel):
    tasks: List[ExtractedTask] = []
    meetings: List[ExtractedMeeting] = []
    availability: List[ExtractedAvailability] = []
    reminders: List[ExtractedReminder] = []