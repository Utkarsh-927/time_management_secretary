import json

from sqlalchemy.orm import Session

from ..schemas.management import ManagementData
from ..database.models import (
    TaskDB,
    MeetingDB,
    AvailabilityDB,
    ReminderDB,
)


def save_management_data(
    db: Session,
    data: ManagementData
) -> dict:
    """
    Save validated ManagementData into the database.
    """

    saved = {
        "tasks": 0,
        "meetings": 0,
        "availability": 0,
        "reminders": 0,
    }

  
    for task in data.tasks:

        db_task = TaskDB(
            title=task.title,
            description=task.description,
            deadline=task.deadline,
            estimated_duration=task.estimated_duration,
            importance=task.importance,
        )

        db.add(db_task)

        saved["tasks"] += 1


    for meeting in data.meetings:

        db_meeting = MeetingDB(
            title=meeting.title,
            description=meeting.description,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            location=meeting.location,
            participants=json.dumps(
                meeting.participants
            ),
        )

        db.add(db_meeting)

        saved["meetings"] += 1


    for availability in data.availability:

        db_availability = AvailabilityDB(
            start_date=availability.start_date,
            end_date=availability.end_date,
            start_time=availability.start_time,
            end_time=availability.end_time,
            recurrence=availability.recurrence,
            weekdays=json.dumps(
                availability.weekdays
            ),
        )

        db.add(db_availability)

        saved["availability"] += 1

   

    for reminder in data.reminders:

        db_reminder = ReminderDB(
            title=reminder.title,
            message=reminder.message,
            reminder_time=reminder.reminder_time,
            reminder_type=reminder.reminder_type,
        )

        db.add(db_reminder)

        saved["reminders"] += 1

    

    db.commit()

    return saved