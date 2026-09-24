from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..models.task import Task
from ..models.meeting import Meeting
from ..models.reminder import Reminder

from .commands import (
    COMMAND_UPDATE_TASK,
    COMMAND_DELETE_TASK,
    COMMAND_UPDATE_MEETING,
    COMMAND_DELETE_MEETING,
    COMMAND_CREATE_REMINDER,
)



WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def get_next_weekday(
    weekday_name: str,
):
    """
    "next Friday" means Friday of the following week.
    """

    weekday_name = (
        weekday_name.strip().lower()
    )

    target = WEEKDAY_NAMES.get(
        weekday_name
    )

    if target is None:
        return None

    today = date.today()

    current_week_start = (
        today
        - timedelta(days=today.weekday())
    )

    next_week_start = (
        current_week_start
        + timedelta(days=7)
    )

    return (
        next_week_start
        + timedelta(days=target)
    )


def get_this_weekday(
    weekday_name: str,
):
    """
    "this Friday" means Friday of the current week.
    """

    weekday_name = (
        weekday_name.strip().lower()
    )

    target = WEEKDAY_NAMES.get(
        weekday_name
    )

    if target is None:
        return None

    today = date.today()

    current_week_start = (
        today
        - timedelta(days=today.weekday())
    )

    return (
        current_week_start
        + timedelta(days=target)
    )


def resolve_date_phrase(
    phrase: str | None,
):
    """
    Convert:

        today
        tomorrow
        yesterday
        Friday
        this Friday
        next Friday

    into a Python date.
    """

    if phrase is None:
        return None

    text = phrase.strip().lower()

    if text == "today":
        return date.today()

    if text == "tomorrow":
        return (
            date.today()
            + timedelta(days=1)
        )

    if text == "yesterday":
        return (
            date.today()
            - timedelta(days=1)
        )


    if text.startswith("next "):

        weekday = text[
            len("next "):
        ].strip()

        return get_next_weekday(
            weekday
        )


    if text.startswith("this "):

        weekday = text[
            len("this "):
        ].strip()

        return get_this_weekday(
            weekday
        )


    if text in WEEKDAY_NAMES:

        target = WEEKDAY_NAMES[
            text
        ]

        today = date.today()

        days_ahead = (
            target
            - today.weekday()
        ) % 7

        return (
            today
            + timedelta(days=days_ahead)
        )


    try:
        return date.fromisoformat(
            text
        )
    except ValueError:
        return None



def find_task(
    db: Session,
    title: str | None,
):
    """
    Find a pending task using a case-insensitive
    exact or partial title match.
    """

    if title is None:
        return None

    normalized = (
        title.strip().lower()
    )

    if not normalized:
        return None

    tasks: list[Task] = (
        db.query(Task)
        .filter(
            Task.status != "completed"
        )
        .all()
    )


    for task in tasks:

        task_title = getattr(
            task,
            "title",
            None,
        )

        if task_title is None:
            continue

        task_title_text = (
            str(task_title)
            .strip()
            .lower()
        )

        if task_title_text == normalized:
            return task

 
    for task in tasks:

        task_title = getattr(
            task,
            "title",
            None,
        )

        if task_title is None:
            continue

        task_title_text = (
            str(task_title)
            .strip()
            .lower()
        )

        if (
            normalized in task_title_text
            or task_title_text in normalized
        ):
            return task

    return None



def find_meeting(
    db: Session,
    title: str | None,
):
    """
    Find the most relevant meeting.

    Exact title match is preferred.
    """

    meetings: list[Meeting] = (
        db.query(Meeting)
        .order_by(
            Meeting.start_time.asc()
        )
        .all()
    )

    if not meetings:
        return None


    if (
        title is None
        or title.strip().lower()
        == "meeting"
    ):
        return meetings[0]

    normalized = (
        title.strip().lower()
    )

    if not normalized:
        return meetings[0]

 
    for meeting in meetings:

        meeting_title = getattr(
            meeting,
            "title",
            None,
        )

        if meeting_title is None:
            continue

        meeting_title_text = (
            str(meeting_title)
            .strip()
            .lower()
        )

        if meeting_title_text == normalized:
            return meeting


    for meeting in meetings:

        meeting_title = getattr(
            meeting,
            "title",
            None,
        )

        if meeting_title is None:
            continue

        meeting_title_text = (
            str(meeting_title)
            .strip()
            .lower()
        )

        if (
            normalized in meeting_title_text
            or meeting_title_text in normalized
        ):
            return meeting

    return None



def execute_update_task(
    db: Session,
    command: dict,
):
    """
    Execute an update_task command.

    Supports:

        importance
        deadline_phrase
    """

    task = find_task(
        db,
        command.get(
            "task_title"
        ),
    )

    if task is None:

        return {
            "success": False,
            "message": "Task not found.",
        }

    changes = (
        command.get("changes")
        or {}
    )

    updated_fields = []


    if "importance" in changes:

        importance = changes[
            "importance"
        ]

        if (
            isinstance(
                importance,
                int,
            )
            and 1 <= importance <= 5
        ):

            setattr(
                task,
                "importance",
                importance,
            )

            updated_fields.append(
                "importance"
            )


    deadline_phrase = changes.get(
        "deadline_phrase"
    )

    if deadline_phrase:

        resolved_date = (
            resolve_date_phrase(
                deadline_phrase
            )
        )

        if resolved_date is None:

            return {
                "success": False,
                "message": (
                    "I could not understand "
                    "the new task date."
                ),
            }

        current_deadline = getattr(
            task,
            "deadline",
            None,
        )

    
        if isinstance(
            current_deadline,
            datetime,
        ):

            new_deadline = (
                datetime.combine(
                    resolved_date,
                    current_deadline.time(),
                )
            )

        else:

            new_deadline = (
                datetime.combine(
                    resolved_date,
                    datetime.min.time(),
                )
            )

        setattr(
            task,
            "deadline",
            new_deadline,
        )

        updated_fields.append(
            "deadline"
        )

 
    if not updated_fields:

        return {
            "success": False,
            "message": (
                "No valid task changes "
                "were found."
            ),
        }

   
    db.commit()
    db.refresh(task)

    task_id = getattr(
        task,
        "id",
        None,
    )

    task_title = getattr(
        task,
        "title",
        None,
    )

    task_deadline = getattr(
        task,
        "deadline",
        None,
    )

    task_importance = getattr(
        task,
        "importance",
        None,
    )

    task_status = getattr(
        task,
        "status",
        None,
    )

    return {
        "success": True,
        "message": (
            "Task updated successfully."
        ),
        "task": {
            "id": task_id,
            "title": task_title,
            "deadline": (
                task_deadline.isoformat()
                if isinstance(
                    task_deadline,
                    datetime,
                )
                else None
            ),
            "importance": task_importance,
            "status": task_status,
        },
        "updated_fields": (
            updated_fields
        ),
    }



def execute_delete_task(
    db: Session,
    command: dict,
):
    """
    Execute delete_task command.
    """

    task = find_task(
        db,
        command.get(
            "task_title"
        ),
    )

    if task is None:

        return {
            "success": False,
            "message": "Task not found.",
        }

    task_id = getattr(
        task,
        "id",
        None,
    )

    task_title = getattr(
        task,
        "title",
        None,
    )

    db.delete(task)
    db.commit()

    return {
        "success": True,
        "message": (
            "Task deleted successfully."
        ),
        "task": {
            "id": task_id,
            "title": task_title,
        },
    }


def execute_update_meeting(
    db: Session,
    command: dict,
):
    """
    Execute update_meeting command.

    Currently supports moving a meeting
    to another date while preserving
    its original duration and time.
    """

    meeting = find_meeting(
        db,
        command.get(
            "meeting_title"
        ),
    )

    if meeting is None:

        return {
            "success": False,
            "message": "Meeting not found.",
        }

    changes = (
        command.get("changes")
        or {}
    )

    date_phrase = changes.get(
        "date_phrase"
    )

    if not date_phrase:

        return {
            "success": False,
            "message": (
                "No new meeting date "
                "was found."
            ),
        }

    resolved_date = (
        resolve_date_phrase(
            date_phrase
        )
    )

    if resolved_date is None:

        return {
            "success": False,
            "message": (
                "I could not understand "
                "the new meeting date."
            ),
        }

    current_start = getattr(
        meeting,
        "start_time",
        None,
    )

    current_end = getattr(
        meeting,
        "end_time",
        None,
    )

    if not isinstance(
        current_start,
        datetime,
    ) or not isinstance(
        current_end,
        datetime,
    ):

        return {
            "success": False,
            "message": (
                "The meeting has an "
                "invalid time range."
            ),
        }


    duration = (
        current_end
        - current_start
    )

    new_start = (
        datetime.combine(
            resolved_date,
            current_start.time(),
        )
    )

    new_end = (
        new_start
        + duration
    )

    setattr(
        meeting,
        "start_time",
        new_start,
    )

    setattr(
        meeting,
        "end_time",
        new_end,
    )

 
    db.commit()
    db.refresh(meeting)

    meeting_id = getattr(
        meeting,
        "id",
        None,
    )

    meeting_title = getattr(
        meeting,
        "title",
        None,
    )

    saved_start = getattr(
        meeting,
        "start_time",
        None,
    )

    saved_end = getattr(
        meeting,
        "end_time",
        None,
    )

    return {
        "success": True,
        "message": (
            "Meeting updated successfully."
        ),
        "meeting": {
            "id": meeting_id,
            "title": meeting_title,
            "start_time": (
                saved_start.isoformat()
                if isinstance(
                    saved_start,
                    datetime,
                )
                else None
            ),
            "end_time": (
                saved_end.isoformat()
                if isinstance(
                    saved_end,
                    datetime,
                )
                else None
            ),
        },
    }



def execute_delete_meeting(
    db: Session,
    command: dict,
):
    """
    Execute delete_meeting command.
    """

    meeting = find_meeting(
        db,
        command.get(
            "meeting_title"
        ),
    )

    if meeting is None:

        return {
            "success": False,
            "message": "Meeting not found.",
        }

    meeting_id = getattr(
        meeting,
        "id",
        None,
    )

    meeting_title = getattr(
        meeting,
        "title",
        None,
    )

    db.delete(meeting)
    db.commit()

    return {
        "success": True,
        "message": (
            "Meeting deleted successfully."
        ),
        "meeting": {
            "id": meeting_id,
            "title": meeting_title,
        },
    }




def execute_create_reminder(
    db: Session,
    command: dict,
):
    """
    Create a reminder before the nearest
    relevant upcoming meeting.
    """

    minutes_before = command.get(
        "minutes_before"
    )

    if not isinstance(
        minutes_before,
        int,
    ):

        return {
            "success": False,
            "message": (
                "Invalid reminder duration."
            ),
        }

    if minutes_before <= 0:

        return {
            "success": False,
            "message": (
                "Reminder duration must "
                "be greater than zero."
            ),
        }

    target = command.get(
        "target"
    )

    meeting = None



    if target == "meeting":

        now = datetime.now()

        meetings: list[Meeting] = (
            db.query(Meeting)
            .filter(
                Meeting.start_time >= now
            )
            .order_by(
                Meeting.start_time.asc()
            )
            .all()
        )

        if meetings:
            meeting = meetings[0]

    if meeting is None:

        return {
            "success": False,
            "message": (
                "No upcoming meeting "
                "was found."
            ),
        }

    meeting_start = getattr(
        meeting,
        "start_time",
        None,
    )

    meeting_id = getattr(
        meeting,
        "id",
        None,
    )

    if not isinstance(
        meeting_start,
        datetime,
    ):

        return {
            "success": False,
            "message": (
                "The meeting has an "
                "invalid start time."
            ),
        }

 

    reminder_time = (
        meeting_start
        - timedelta(
            minutes=minutes_before
        )
    )



    reminder = Reminder(
        title="Meeting Reminder",
        message=command.get(
            "message"
        ),
        reminder_time=reminder_time,
        reminder_type="before_event",
        related_id=meeting_id,
        status="pending",
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    reminder_id = getattr(
        reminder,
        "id",
        None,
    )

    saved_reminder_time = getattr(
        reminder,
        "reminder_time",
        None,
    )

    reminder_type = getattr(
        reminder,
        "reminder_type",
        None,
    )

    related_id = getattr(
        reminder,
        "related_id",
        None,
    )

    status = getattr(
        reminder,
        "status",
        None,
    )

    return {
        "success": True,
        "message": (
            "Reminder created successfully."
        ),
        "reminder": {
            "id": reminder_id,
            "title": "Meeting Reminder",
            "reminder_time": (
                saved_reminder_time.isoformat()
                if isinstance(
                    saved_reminder_time,
                    datetime,
                )
                else None
            ),
            "reminder_type": reminder_type,
            "related_id": related_id,
            "status": status,
        },
    }




def execute_command(
    db: Session,
    command: dict,
):
    """
    Execute a detected management command.
    """

    intent = command.get(
        "intent"
    )


    if intent == COMMAND_UPDATE_TASK:

        return execute_update_task(
            db,
            command,
        )



    if intent == COMMAND_DELETE_TASK:

        return execute_delete_task(
            db,
            command,
        )



    if intent == COMMAND_UPDATE_MEETING:

        return execute_update_meeting(
            db,
            command,
        )


    if intent == COMMAND_DELETE_MEETING:

        return execute_delete_meeting(
            db,
            command,
        )



    if intent == COMMAND_CREATE_REMINDER:

        return execute_create_reminder(
            db,
            command,
        )



    return {
        "success": False,
        "message": (
            "No executable command was found."
        ),
    }




if __name__ == "__main__":

    print(
        "Command executor module loaded successfully."
    )