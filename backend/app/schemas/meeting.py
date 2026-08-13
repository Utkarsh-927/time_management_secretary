from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    participants: Optional[str] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    participants: Optional[str] = None
    status: Optional[str] = None


class MeetingResponse(MeetingCreate):
    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)