from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.task import Task
from ..models.meeting import Meeting
from ..models.availability import Availability
from ..models.reminder import Reminder
from ..services.planner import create_plan



router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)



def calculate_available_minutes(
    availability_list,
    target_date
):
    """
    Calculate the total available minutes
    for a specific date.

    Supports:

    - none
    - daily
    - weekly

    For weekly availability, only matching
    weekdays are counted.
    """

    total_minutes = 0

    weekday_name = target_date.strftime("%A")

    for availability in availability_list:

        if (
            availability.start_date is None
            or availability.end_date is None
        ):
            continue

        if (
            availability.start_time is None
            or availability.end_time is None
        ):
            continue

        
        if target_date < availability.start_date:
            continue

        if target_date > availability.end_date:
            continue

        
        recurrence = (
            availability.recurrence
            or "none"
        )

        if recurrence == "weekly":

            weekdays = (
                availability.weekdays
                or ""
            )

            if isinstance(
                weekdays,
                str
            ):
                weekdays = [
                    day.strip()
                    for day in weekdays.split(",")
                    if day.strip()
                ]

            if weekday_name not in weekdays:
                continue

        elif recurrence not in (
            "none",
            "daily",
        ):
            continue

        
        start_datetime = datetime.combine(
            target_date,
            availability.start_time
        )

        end_datetime = datetime.combine(
            target_date,
            availability.end_time
        )

        if end_datetime <= start_datetime:
            continue

        total_minutes += int(
            (
                end_datetime
                - start_datetime
            ).total_seconds()
            / 60
        )

    return total_minutes



@router.get("")
def get_dashboard(
    db: Session = Depends(get_db)
):
    """
    Return all information required by the
    management dashboard.

    Existing dashboard fields are preserved.

    Additional analytics include:

    - completed tasks
    - pending tasks
    - overdue tasks
    - upcoming meetings
    - upcoming reminders
    - scheduled minutes
    - available minutes
    """

    today = date.today()

    start_of_day = datetime.combine(
        today,
        time.min
    )

    end_of_day = datetime.combine(
        today,
        time.max
    )

    
    all_tasks = (
        db.query(Task)
        .all()
    )

    
    tasks = (
        db.query(Task)
        .filter(
            Task.status != "completed",
            Task.deadline.is_(None)
            | (
                Task.deadline >= start_of_day
            )
        )
        .order_by(
            Task.deadline.asc()
        )
        .all()
    )

    
    completed_tasks = (
        db.query(Task)
        .filter(
            Task.status == "completed"
        )
        .count()
    )

    
    pending_tasks = (
        db.query(Task)
        .filter(
            Task.status != "completed"
        )
        .count()
    )

    
    overdue_tasks = (
        db.query(Task)
        .filter(
            Task.status != "completed",
            Task.deadline.is_not(None),
            Task.deadline < datetime.now()
        )
        .count()
    )

    meetings = (
        db.query(Meeting)
        .filter(
            Meeting.start_time >= start_of_day,
            Meeting.start_time <= end_of_day
        )
        .order_by(
            Meeting.start_time
        )
        .all()
    )

    
    upcoming_meetings = (
        db.query(Meeting)
        .filter(
            Meeting.start_time >= datetime.now()
        )
        .count()
    )

    
    availability = (
        db.query(Availability)
        .filter(
            Availability.start_date <= today,
            Availability.end_date >= today
        )
        .all()
    )

    
    all_availability = (
        db.query(Availability)
        .all()
    )

    
    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.status == "pending"
        )
        .order_by(
            Reminder.reminder_time.asc()
        )
        .all()
    )

    
    upcoming_reminders = (
        db.query(Reminder)
        .filter(
            Reminder.status == "pending",
            Reminder.reminder_time.is_not(None),
            Reminder.reminder_time >= datetime.now()
        )
        .count()
    )

    
    all_tasks = (
        db.query(Task)
        .filter(
            Task.status != "completed"
        )
        .all()
    )

    all_availability = (
        db.query(Availability)
        .all()
    )

    all_meetings = (
        db.query(Meeting)
        .all()
    )

    plan = create_plan(
        tasks=all_tasks,
        availability=all_availability,
        meetings=all_meetings
    )
    
    scheduled_minutes = sum(
        item.get(
            "duration_minutes",
            0
        )
        for item in plan.get(
            "schedule",
            []
        )
    )

    
    available_minutes = (
        calculate_available_minutes(
            availability_list=all_availability,
            target_date=today
        )
    )

    
    return {

        
        "date": today.isoformat(),

        
        "tasks": [
            {
                "id": task.id,

                "title": task.title,

                "description": task.description,

                "deadline": (
                    task.deadline.isoformat()
                    if task.deadline is not None
                    else None
                ),

                "estimated_duration": (
                    task.estimated_duration
                ),

                "importance": task.importance,

                "priority_score": (
                    task.priority_score
                ),

                "status": task.status,

                "completed_at": (
                    task.completed_at.isoformat()
                    if getattr(
                        task,
                        "completed_at",
                        None
                    ) is not None
                    else None
                )
            }

            for task in tasks
        ],

        
        "meetings": [
            {
                "id": meeting.id,

                "title": meeting.title,

                "description": meeting.description,

                "start_time": (
                    meeting.start_time.isoformat()
                    if meeting.start_time is not None
                    else None
                ),

                "end_time": (
                    meeting.end_time.isoformat()
                    if meeting.end_time is not None
                    else None
                ),

                "location": meeting.location,

                "participants": (
                    meeting.participants
                )
            }

            for meeting in meetings
        ],

       
        "availability": [
            {
                "id": item.id,

                "start_date": (
                    item.start_date.isoformat()
                    if item.start_date is not None
                    else None
                ),

                "end_date": (
                    item.end_date.isoformat()
                    if item.end_date is not None
                    else None
                ),

                "start_time": (
                    item.start_time.isoformat()
                    if item.start_time is not None
                    else None
                ),

                "end_time": (
                    item.end_time.isoformat()
                    if item.end_time is not None
                    else None
                ),

                "recurrence": item.recurrence,

                "weekdays": item.weekdays
            }

            for item in availability
        ],

       
        "reminders": [
            {
                "id": reminder.id,

                "title": reminder.title,

                "message": reminder.message,

                "reminder_time": (
                    reminder.reminder_time.isoformat()
                    if reminder.reminder_time is not None
                    else None
                ),

                "reminder_type": (
                    reminder.reminder_type
                ),

                "related_id": reminder.related_id,

                "status": reminder.status
            }

            for reminder in reminders
        ],

       
        "plan": plan,

        
        "analytics": {

            "completed_tasks": (
                completed_tasks
            ),

            "pending_tasks": (
                pending_tasks
            ),

            "overdue_tasks": (
                overdue_tasks
            ),

            "upcoming_meetings": (
                upcoming_meetings
            ),

            "upcoming_reminders": (
                upcoming_reminders
            ),

            "scheduled_minutes": (
                scheduled_minutes
            ),

            "available_minutes": (
                available_minutes
            )
        }
    }