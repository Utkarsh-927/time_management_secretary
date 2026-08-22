from datetime import date, time
from typing import Optional

from pydantic import BaseModel


class AvailabilityBase(BaseModel):
    start_date: date
    end_date: date

    start_time: time
    end_time: time

    recurrence: str = "none"

    weekdays: Optional[str] = None


class AvailabilityCreate(AvailabilityBase):
    pass


class AvailabilityUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    recurrence: Optional[str] = None

    weekdays: Optional[str] = None


class AvailabilityResponse(AvailabilityBase):
    id: int

    class Config:
        from_attributes = True