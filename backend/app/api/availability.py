from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.availability import Availability
from ..schemas.availability import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailabilityUpdate
)


router = APIRouter(
    prefix="/availability",
    tags=["Availability"]
)


def validate_availability(
    start_date,
    end_date,
    start_time,
    end_time,
    recurrence,
    weekdays
):
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date must be after or equal to start date"
        )

    if start_time and end_time:
        if end_time <= start_time:
            raise HTTPException(
                status_code=400,
                detail="End time must be after start time"
            )

    valid_recurrence = {
        "none",
        "daily",
        "weekly"
    }

    if recurrence not in valid_recurrence:
        raise HTTPException(
            status_code=400,
            detail="Recurrence must be none, daily, or weekly"
        )

    if recurrence == "weekly" and not weekdays:
        raise HTTPException(
            status_code=400,
            detail="Weekdays are required for weekly recurrence"
        )


# crete availibility

@router.post(
    "/",
    response_model=AvailabilityResponse
)
def create_availability(
    availability_data: AvailabilityCreate,
    db: Session = Depends(get_db)
):

    validate_availability(
        availability_data.start_date,
        availability_data.end_date,
        availability_data.start_time,
        availability_data.end_time,
        availability_data.recurrence,
        availability_data.weekdays
    )

    availability = Availability(
        start_date=availability_data.start_date,
        end_date=availability_data.end_date,
        start_time=availability_data.start_time,
        end_time=availability_data.end_time,
        recurrence=availability_data.recurrence,
        weekdays=availability_data.weekdays
    )

    db.add(availability)
    db.commit()
    db.refresh(availability)

    return availability



# GET ALL availability



@router.get(
    "/",
    response_model=List[AvailabilityResponse]
)
def get_availability(
    db: Session = Depends(get_db)
):

    availability = (
        db.query(Availability)
        .order_by(Availability.start_date)
        .all()
    )

    return availability



# GET SINGLE AVAILABILITY


@router.get(
    "/{availability_id}",
    response_model=AvailabilityResponse
)
def get_availability_by_id(
    availability_id: int,
    db: Session = Depends(get_db)
):

    availability = (
        db.query(Availability)
        .filter(
            Availability.id == availability_id
        )
        .first()
    )

    if availability is None:
        raise HTTPException(
            status_code=404,
            detail="Availability record not found"
        )

    return availability


# for update availability

@router.put(
    "/{availability_id}",
    response_model=AvailabilityResponse
)
def update_availability(
    availability_id: int,
    availability_data: AvailabilityUpdate,
    db: Session = Depends(get_db)
):

    availability = (
        db.query(Availability)
        .filter(
            Availability.id == availability_id
        )
        .first()
    )

    if availability is None:
        raise HTTPException(
            status_code=404,
            detail="Availability record not found"
        )

    update_data = availability_data.model_dump(
        exclude_unset=True
    )

    new_start_date = update_data.get(
        "start_date",
        availability.start_date
    )

    new_end_date = update_data.get(
        "end_date",
        availability.end_date
    )

    new_start_time = update_data.get(
        "start_time",
        availability.start_time
    )

    new_end_time = update_data.get(
        "end_time",
        availability.end_time
    )

    new_recurrence = update_data.get(
        "recurrence",
        availability.recurrence
    )

    new_weekdays = update_data.get(
        "weekdays",
        availability.weekdays
    )

    validate_availability(
        new_start_date,
        new_end_date,
        new_start_time,
        new_end_time,
        new_recurrence,
        new_weekdays
    )

    for key, value in update_data.items():
        setattr(availability, key, value)

    db.commit()
    db.refresh(availability)

    return availability


# delete availability

@router.delete("/{availability_id}")
def delete_availability(
    availability_id: int,
    db: Session = Depends(get_db)
):

    availability = (
        db.query(Availability)
        .filter(
            Availability.id == availability_id
        )
        .first()
    )

    if availability is None:
        raise HTTPException(
            status_code=404,
            detail="Availability record not found"
        )

    db.delete(availability)
    db.commit()

    return {
        "message": "Availability deleted successfully",
        "availability_id": availability_id
    }