from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models.reminder import Reminder
def calculate_reminder_time(
    event_time: datetime,
    minutes_before: int
) -> datetime:
    """
    Calculate when a reminder should trigger
    before an event.
    """

    return event_time - timedelta(
        minutes=minutes_before
    )


def create_before_event_reminder(
    event_time: datetime,
    minutes_before: int,
    title: str = "Event Reminder",
    message: str | None = None,
    related_id: int | None = None
) -> dict:
    """
    Create a reminder scheduled before an event.
    """

    reminder_time = calculate_reminder_time(
        event_time,
        minutes_before
    )

    return {
        "title": title,
        "message": message,
        "reminder_time": reminder_time,
        "reminder_type": "before_event",
        "related_id": related_id,
        "status": "pending"
    }



def save_reminder(
    db: Session,
    event_time: datetime,
    minutes_before: int,
    title: str = "Event Reminder",
    message: str | None = None,
    related_id: int | None = None
):
    """
    Calculate the reminder time and save
    the reminder to the database.
    """

    reminder_time = calculate_reminder_time(
        event_time,
        minutes_before
    )

    reminder = Reminder(
        title=title,
        message=message,
        reminder_time=reminder_time,
        reminder_type="before_event",
        related_id=related_id,
        status="pending"
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    return reminder
def process_reminders(
    db: Session,
    reminders: list,
    meetings: list
):
    """
    Convert parsed reminders into database reminders.

    Currently supports reminders that occur
    before a meeting.
    """

    created_reminders = []

    for reminder_data in reminders:

        if not isinstance(reminder_data, dict):
            continue

        if reminder_data.get("reminder_type") != "before_event":
            continue

        # --------------------------------------------------
        # Find the related meeting
        # --------------------------------------------------

        meeting = None

        for item in meetings:
            if item.start_time is not None:
                meeting = item
                break

        if meeting is None:
            continue

        if meeting.start_time is None:
            continue

        # --------------------------------------------------
        # Extract "30 minutes before" from reminder text
        # --------------------------------------------------

        message = (
            reminder_data.get("message")
            or ""
        )

        import re

        match = re.search(
            r"(\d+)\s*minutes?\s*before",
            message,
            re.IGNORECASE
        )

        if not match:
            continue

        minutes_before = int(
            match.group(1)
        )

        # --------------------------------------------------
        # Save reminder
        # --------------------------------------------------

        reminder = save_reminder(
            db=db,
            event_time=meeting.start_time,
            minutes_before=minutes_before,
            title=(
                reminder_data.get("title")
                or "Meeting Reminder"
            ),
            message=message,
            related_id=meeting.id
        )

        created_reminders.append(reminder)

    return created_reminders