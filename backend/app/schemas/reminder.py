from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReminderCreate(BaseModel):
    title: str

    message: Optional[str] = None

    reminder_time: datetime

    reminder_type: str = "general"

    related_id: Optional[int] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = None

    message: Optional[str] = None

    reminder_time: Optional[datetime] = None

    reminder_type: Optional[str] = None

    related_id: Optional[int] = None

    status: Optional[str] = None


class ReminderResponse(ReminderCreate):
    id: int

    status: str

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )