from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.meeting import Meeting
from ..schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    MeetingUpdate,
)


router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"]
)



@router.post(
    "/",
    response_model=MeetingResponse,
    status_code=201
)
def create_meeting(
    meeting_data: MeetingCreate,
    db: Session = Depends(get_db)
):
    # Validate meeting time
    if meeting_data.end_time <= meeting_data.start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    meeting = Meeting(
        title=meeting_data.title,
        description=meeting_data.description,
        start_time=meeting_data.start_time,
        end_time=meeting_data.end_time,
        location=meeting_data.location,
        participants=meeting_data.participants
    )

    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return meeting



@router.get(
    "/",
    response_model=List[MeetingResponse]
)
def get_meetings(
    db: Session = Depends(get_db)
):
    meetings = (
        db.query(Meeting)
        .order_by(Meeting.start_time.asc())
        .all()
    )

    return meetings



@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse
)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db)
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id)
        .first()
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    return meeting



@router.put(
    "/{meeting_id}",
    response_model=MeetingResponse
)
def update_meeting(
    meeting_id: int,
    meeting_data: MeetingUpdate,
    db: Session = Depends(get_db)
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id)
        .first()
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    update_data = meeting_data.model_dump(
        exclude_unset=True
    )

    # Check resulting start/end times
    new_start_time = update_data.get(
        "start_time",
        meeting.start_time
    )

    new_end_time = update_data.get(
        "end_time",
        meeting.end_time
    )

    if new_end_time <= new_start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    # Apply changes
    for key, value in update_data.items():
        setattr(meeting, key, value)

    db.commit()
    db.refresh(meeting)

    return meeting



@router.delete(
    "/{meeting_id}"
)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db)
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id)
        .first()
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    db.delete(meeting)
    db.commit()

    return {
        "message": "Meeting deleted successfully",
        "meeting_id": meeting_id
    }