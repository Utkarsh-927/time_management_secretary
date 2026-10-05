from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..models.task import Task
from ..models.meeting import Meeting
from ..models.event import Event
from ..models.reminder import Reminder


def _day_range(target_date):
    """
    Return the start and exclusive end datetime for a calendar day.
    """
    start = datetime.combine(target_date, time.min)
    end = start + timedelta(days=1)

    return start, end


def _deduplicate_items(items):
    """
    Remove duplicate schedule records without modifying the database.
    """

    seen = set()
    unique = []

    for item in items:
        title = getattr(item, "title", "") or ""
        item_type = getattr(item, "event_type", "") or ""
        event_time = getattr(item, "event_time", None)

        key = (
            item_type.strip().lower(),
            title.strip().lower(),
            event_time,
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


def get_schedule_for_date(
    db: Session,
    user_id: str,
    target_date,
) -> dict[str, Any]:
    """
    Retrieve everything relevant to a user's schedule for one day.

    Sources:
    - tasks
    - meetings
    - events
    - pending reminders
    """

    start, end = _day_range(target_date)

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.deadline >= start,
            Task.deadline < end,
        )
        .order_by(Task.deadline.asc())
        .all()
    )

    meetings = (
        db.query(Meeting)
        .filter(
            Meeting.user_id == user_id,
            Meeting.start_time >= start,
            Meeting.start_time < end,
        )
        .order_by(Meeting.start_time.asc())
        .all()
    )

    events = (
        db.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.event_time >= start,
            Event.event_time < end,
        )
        .order_by(Event.event_time.asc())
        .all()
    )

    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.user_id == user_id,
            Reminder.reminder_time >= start,
            Reminder.reminder_time < end,
            Reminder.status == "pending",
        )
        .order_by(Reminder.reminder_time.asc())
        .all()
    )

    return {
        "date": target_date.isoformat(),
        "tasks": _deduplicate_items(tasks),
        "meetings": _deduplicate_items(meetings),
        "events": _deduplicate_items(events),
        "reminders": _deduplicate_items(reminders),
        "counts": {
            "tasks": len(_deduplicate_items(tasks)),
            "meetings": len(_deduplicate_items(meetings)),
            "events": len(_deduplicate_items(events)),
            "reminders": len(_deduplicate_items(reminders)),
        },
    }


def get_meetings_for_date(
    db: Session,
    user_id: str,
    target_date,
) -> list[Meeting]:
    """
    Retrieve meetings starting on a specific date.
    """

    start, end = _day_range(target_date)

    return (
        db.query(Meeting)
        .filter(
            Meeting.user_id == user_id,
            Meeting.start_time >= start,
            Meeting.start_time < end,
        )
        .order_by(Meeting.start_time.asc())
        .all()
    )


def get_events_for_date(
    db: Session,
    user_id: str,
    target_date,
) -> list[Event]:
    """
    Retrieve events occurring on a specific date.
    """

    start, end = _day_range(target_date)

    return (
        db.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.event_time >= start,
            Event.event_time < end,
        )
        .order_by(Event.event_time.asc())
        .all()
    )


def get_reminders_for_date(
    db: Session,
    user_id: str,
    target_date,
) -> list[Reminder]:
    """
    Retrieve pending reminders scheduled for a specific date.
    """

    start, end = _day_range(target_date)

    return (
        db.query(Reminder)
        .filter(
            Reminder.user_id == user_id,
            Reminder.reminder_time >= start,
            Reminder.reminder_time < end,
            Reminder.status == "pending",
        )
        .order_by(Reminder.reminder_time.asc())
        .all()
    )