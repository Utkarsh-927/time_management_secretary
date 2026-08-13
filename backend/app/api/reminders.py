from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.reminder import Reminder
from ..schemas.reminder import (
    ReminderCreate,
    ReminderResponse,
    ReminderUpdate
)


router = APIRouter(
    prefix="/reminders",
    tags=["Reminders"]
)


# to create reminder

@router.post(
    "/",
    response_model=ReminderResponse
)
def create_reminder(
    reminder_data: ReminderCreate,
    db: Session = Depends(get_db)
):

    reminder = Reminder(
        title=reminder_data.title,
        message=reminder_data.message,
        reminder_time=reminder_data.reminder_time,
        reminder_type=reminder_data.reminder_type,
        related_id=reminder_data.related_id
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    return reminder


# GET all reminder

@router.get(
    "/",
    response_model=List[ReminderResponse]
)
def get_reminders(
    db: Session = Depends(get_db)
):

    reminders = (
        db.query(Reminder)
        .order_by(Reminder.reminder_time)
        .all()
    )

    return reminders


# GET reminder (single)

@router.get(
    "/{reminder_id}",
    response_model=ReminderResponse
)
def get_reminder(
    reminder_id: int,
    db: Session = Depends(get_db)
):

    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id)
        .first()
    )

    if reminder is None:
        raise HTTPException(
            status_code=404,
            detail="Reminder not found"
        )

    return reminder


# for update reminder
@router.put(
    "/{reminder_id}",
    response_model=ReminderResponse
)
def update_reminder(
    reminder_id: int,
    reminder_data: ReminderUpdate,
    db: Session = Depends(get_db)
):

    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id)
        .first()
    )

    if reminder is None:
        raise HTTPException(
            status_code=404,
            detail="Reminder not found"
        )

    update_data = reminder_data.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(reminder, key, value)

    db.commit()
    db.refresh(reminder)

    return reminder


# for marking remindered task completed

@router.patch(
    "/{reminder_id}/complete",
    response_model=ReminderResponse
)
def complete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db)
):

    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id)
        .first()
    )

    if reminder is None:
        raise HTTPException(
            status_code=404,
            detail="Reminder not found"
        )

    reminder.status = "completed"

    db.commit()
    db.refresh(reminder)

    return reminder

# for delete reminder

@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db)
):

    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id)
        .first()
    )

    if reminder is None:
        raise HTTPException(
            status_code=404,
            detail="Reminder not found"
        )

    db.delete(reminder)
    db.commit()

    return {
        "message": "Reminder deleted successfully",
        "reminder_id": reminder_id
    }