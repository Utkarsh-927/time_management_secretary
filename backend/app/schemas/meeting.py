from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    participants: Optional[str] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    participants: Optional[str] = None


class MeetingResponse(MeetingBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )