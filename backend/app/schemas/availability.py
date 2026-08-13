from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AvailabilityCreate(BaseModel):
    start_date: date
    end_date: date

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    recurrence: str = "none"

    weekdays: Optional[str] = None


class AvailabilityUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    recurrence: Optional[str] = None

    weekdays: Optional[str] = None


class AvailabilityResponse(AvailabilityCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )