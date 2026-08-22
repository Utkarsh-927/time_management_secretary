from datetime import date, time, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database.database import get_db

# ============================================================
# AI PARSER
# ============================================================

from ..ai.parser import extract_information

# ============================================================
# AI COMMAND SYSTEM
# ============================================================

from ..ai.commands import detect_command
from ..ai.command_executor import execute_command

# ============================================================
# SCHEMAS
# ============================================================

from ..schemas.management import ManagementData

# ============================================================
# SERVICES
# ============================================================

from ..services.reminder import process_reminders

# ============================================================
# MODELS
# ============================================================

from ..models.task import Task
from ..models.meeting import Meeting
from ..models.availability import Availability


# ============================================================
# SETTINGS
# ============================================================

PLANNING_HORIZON_DAYS = 30


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/ai",
    tags=["AI Management"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AIMessageRequest(BaseModel):
    message: str


# ============================================================
# NORMALIZE DATE
# ============================================================

def normalize_date(value):
    """
    Convert AI-generated date values into
    Python date objects.

    Supports:

        today
        tomorrow
        yesterday
        YYYY-MM-DD
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip().lower()

    today = date.today()

    if value == "today":
        return today

    if value == "tomorrow":
        return today + timedelta(days=1)

    if value == "yesterday":
        return today - timedelta(days=1)

    # --------------------------------------------------------
    # YYYY-MM-DD
    # --------------------------------------------------------

    try:
        return date.fromisoformat(value)

    except ValueError:
        pass

    return None


# ============================================================
# NORMALIZE TIME
# ============================================================

def normalize_time(value):
    """
    Convert values such as:

        3 PM
        5 PM
        5:30 PM
        17:00

    into Python datetime.time objects.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.time()

    if isinstance(value, time):
        return value

    value = str(value).strip()

    formats = [
        "%I %p",
        "%I:%M %p",
        "%I:%M:%S %p",
        "%H:%M",
        "%H:%M:%S",
    ]

    for fmt in formats:

        try:
            return datetime.strptime(
                value,
                fmt
            ).time()

        except ValueError:
            continue

    return None


# ============================================================
# NORMALIZE DATETIME
# ============================================================

def normalize_datetime(
    value,
    fallback_date=None
):
    """
    Convert AI-generated datetime values into
    Python datetime objects.

    Supports:

        tomorrow
        today
        yesterday
        tomorrow 3 PM
        tomorrow 3:00 PM
        today 5 PM
        yesterday 10 AM
        3 PM
        5:30 PM
        2026-08-17 15:00:00
        2026-08-17T15:00:00
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):

        return datetime.combine(
            value,
            time.min
        )

    value = str(value).strip()

    value_lower = value.lower().strip()

    target_date = fallback_date

    # ========================================================
    # STANDALONE RELATIVE DATES
    # ========================================================

    if value_lower == "tomorrow":

        target_date = (
            date.today()
            + timedelta(days=1)
        )

        return datetime.combine(
            target_date,
            time.min
        )

    if value_lower == "today":

        target_date = date.today()

        return datetime.combine(
            target_date,
            time.min
        )

    if value_lower == "yesterday":

        target_date = (
            date.today()
            - timedelta(days=1)
        )

        return datetime.combine(
            target_date,
            time.min
        )

    # ========================================================
    # RELATIVE DATE + TIME
    # ========================================================

    if "tomorrow" in value_lower:

        target_date = (
            date.today()
            + timedelta(days=1)
        )

        value = value_lower.replace(
            "tomorrow",
            ""
        ).strip()

    elif "today" in value_lower:

        target_date = date.today()

        value = value_lower.replace(
            "today",
            ""
        ).strip()

    elif "yesterday" in value_lower:

        target_date = (
            date.today()
            - timedelta(days=1)
        )

        value = value_lower.replace(
            "yesterday",
            ""
        ).strip()

    # ========================================================
    # ISO DATETIME
    # ========================================================

    try:

        return datetime.fromisoformat(
            value
        )

    except ValueError:
        pass

    # ========================================================
    # STANDARD DATETIME FORMATS
    # ========================================================

    formats = [
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %I %p",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %I:%M %p",
        "%d-%m-%Y %H:%M",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt
            )

        except ValueError:
            continue

    # ========================================================
    # TIME ONLY
    # ========================================================

    parsed_time = normalize_time(
        value
    )

    if (
        parsed_time is not None
        and target_date is not None
    ):

        return datetime.combine(
            target_date,
            parsed_time
        )

    return None


# ============================================================
# NORMALIZE DEADLINE
# ============================================================

def normalize_deadline(
    value,
    fallback_date=None
):
    """
    Normalize a task deadline.

    Date-only values such as:

        today
        tomorrow
        yesterday

    represent the END of that day rather than
    midnight at the beginning of that day.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):

        return datetime.combine(
            value,
            time.max
        )

    text = str(value).strip().lower()

    if text == "tomorrow":

        target_date = (
            date.today()
            + timedelta(days=1)
        )

        return datetime.combine(
            target_date,
            time.max
        )

    if text == "today":

        return datetime.combine(
            date.today(),
            time.max
        )

    if text == "yesterday":

        target_date = (
            date.today()
            - timedelta(days=1)
        )

        return datetime.combine(
            target_date,
            time.max
        )

    return normalize_datetime(
        value,
        fallback_date
    )


# ============================================================
# NORMALIZE WEEKDAYS
# ============================================================

def normalize_weekdays(value):
    """
    Convert weekday values into the database
    string format.

    Example:

        ["Monday", "Wednesday", "Friday"]

    becomes:

        "Monday,Wednesday,Friday"
    """

    if value is None:
        return None

    if isinstance(value, list):

        cleaned = []

        for day in value:

            day = str(day).strip()

            if day.lower() in (
                "unspecified",
                "none",
                "null",
            ):
                continue

            if day:
                cleaned.append(day)

        if not cleaned:
            return None

        return ",".join(cleaned)

    value = str(value).strip()

    if value.lower() in (
        "",
        "unspecified",
        "none",
        "null",
    ):
        return None

    return value


# ============================================================
# EXTRACT WEEKDAYS FROM MESSAGE
# ============================================================

def weekdays_from_message(
    message: str
):
    """
    Deterministically extract weekdays from
    the original user message.

    Examples:

        Monday, Wednesday and Friday

        every Monday Wednesday Friday

        Monday to Friday
    """

    text = message.lower()

    weekday_map = {
        "monday": "Monday",
        "tuesday": "Tuesday",
        "wednesday": "Wednesday",
        "thursday": "Thursday",
        "friday": "Friday",
        "saturday": "Saturday",
        "sunday": "Sunday",
    }

    # ========================================================
    # MONDAY TO FRIDAY
    # ========================================================

    if (
        "monday to friday" in text
        or "monday through friday" in text
        or "mon to fri" in text
    ):

        return [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
        ]

    # ========================================================
    # INDIVIDUAL WEEKDAYS
    # ========================================================

    found = []

    for raw_name, proper_name in (
        weekday_map.items()
    ):

        if raw_name in text:
            found.append(proper_name)

    if not found:
        return None

    # Keep calendar order.

    weekday_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    found.sort(
        key=weekday_order.index
    )

    return found


# ============================================================
# GET DATE FROM USER MESSAGE
# ============================================================

def get_message_date(
    message: str
):
    """
    Determine the likely date from the user's
    natural-language message.

    Supports:

        today
        tomorrow
        yesterday

    Default:

        today
    """

    message_lower = message.lower()

    if "tomorrow" in message_lower:

        return (
            date.today()
            + timedelta(days=1)
        )

    if "yesterday" in message_lower:

        return (
            date.today()
            - timedelta(days=1)
        )

    return date.today()


# ============================================================
# DETERMINE AVAILABILITY RECURRENCE
# ============================================================

def normalize_recurrence(
    recurrence,
    message: str,
    weekdays
):
    """
    Determine availability recurrence.

    Explicit user wording has priority over
    model-generated recurrence.
    """

    message_lower = message.lower()

    # ========================================================
    # DAILY
    # ========================================================

    if "every day" in message_lower:
        return "daily"

    if "each day" in message_lower:
        return "daily"

    if "daily" in message_lower:
        return "daily"

    # ========================================================
    # WEEKLY
    # ========================================================

    if "every week" in message_lower:
        return "weekly"

    if "each week" in message_lower:
        return "weekly"

    if "weekly" in message_lower:
        return "weekly"

    # ========================================================
    # EXPLICIT WEEKDAYS
    # ========================================================

    if weekdays:
        return "weekly"

    # ========================================================
    # FALLBACK
    # ========================================================

    if recurrence in (
        "daily",
        "weekly",
    ):
        return recurrence

    return "none"


# ============================================================
# AI PROCESSING ENDPOINT
# ============================================================

@router.post("/process")
def process_message(
    request: AIMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Process a natural-language message.

    Two paths are supported:

    1. Management commands
       -> update/delete/create reminder

    2. Normal AI extraction
       -> create tasks, meetings,
          availability and reminders
    """

    # ========================================================
    # VALIDATE MESSAGE
    # ========================================================

    if not request.message.strip():

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    # ========================================================
    # 0. DETECT MANAGEMENT COMMAND
    # ========================================================

    try:

        command = detect_command(
            request.message
        )

        print(
            "\n========== COMMAND DETECTION =========="
        )

        print(command)

        print(
            "=======================================\n"
        )

    except Exception as error:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Command detection failed: "
                f"{type(error).__name__}: {error}"
            )
        )

    # ========================================================
    # COMMAND PATH
    # ========================================================

    if command.get("intent") != "none":

        try:

            command_result = execute_command(
                db=db,
                command=command,
            )

        except Exception as error:

            db.rollback()

            import traceback

            traceback.print_exc()

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Command execution failed: "
                    f"{type(error).__name__}: {error}"
                )
            )

        # ----------------------------------------------------
        # Return command result
        # ----------------------------------------------------

        return {
            "message": command_result.get(
                "message",
                "Command processed."
            ),

            "command_processed": True,

            "command": command,

            "result": command_result,

            "created": {
                "tasks": 0,
                "meetings": 0,
                "availability": 0,
                "reminders": (
                    1
                    if (
                        command_result.get(
                            "success"
                        )
                        and command.get(
                            "intent"
                        )
                        == "create_reminder"
                    )
                    else 0
                ),
            },
        }

    # ========================================================
    # NORMAL AI PATH
    # ========================================================

    # ========================================================
    # 1. RUN LOCAL GEMMA
    # ========================================================

    try:

        raw_data = extract_information(
            request.message
        )

        print(
            "\n========== AI RAW DATA =========="
        )

        print(
            raw_data
        )

        print(
            "=================================\n"
        )

    except Exception as error:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"AI processing failed: "
                f"{type(error).__name__}: {error}"
            )
        )

    # ========================================================
    # 2. PYDANTIC VALIDATION
    # ========================================================

    try:

        data = ManagementData.model_validate(
            raw_data
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"AI returned invalid data: "
                f"{error}"
            )
        )

    # ========================================================
    # FALLBACK DATE
    # ========================================================

    message_date = get_message_date(
        request.message
    )

    # ========================================================
    # 3. SAVE TASKS
    # ========================================================

    created_tasks = []
    duplicate_tasks = []

    for task_data in data.tasks:

        deadline = task_data.deadline

        if deadline is not None:

            if isinstance(
                deadline,
                str
            ):

                deadline = normalize_deadline(
                    deadline,
                    message_date
                )

        # ====================================================
        # DUPLICATE TASK DETECTION
        # ====================================================

        task_title = (
            task_data.title or ""
        ).strip()

        normalized_title = (
            task_title.lower()
        )

        existing_tasks = (
            db.query(Task)
            .filter(
                Task.status != "completed"
            )
            .all()
        )

        duplicate = None

        for existing_task in existing_tasks:

            existing_title = (
                getattr(
                    existing_task,
                    "title",
                    ""
                )
                or ""
            ).strip().lower()

            # Exact title match

            if normalized_title == existing_title:

                # --------------------------------------------
                # Compare deadlines
                # --------------------------------------------

                same_deadline = False

                existing_deadline = getattr(
                    existing_task,
                    "deadline",
                    None
                )

                if (
                    deadline is None
                    and existing_deadline is None
                ):

                    same_deadline = True

                elif (
                    deadline is not None
                    and existing_deadline is not None
                ):

                    difference = abs(
                        (
                            existing_deadline
                            - deadline
                        ).total_seconds()
                    )

                    same_deadline = (
                        difference <= 60
                    )

                # --------------------------------------------
                # Same task = duplicate
                # --------------------------------------------

                if same_deadline:

                    duplicate = (
                        existing_task
                    )

                    break

        # ====================================================
        # HANDLE DUPLICATE
        # ====================================================

        if duplicate is not None:

            duplicate_tasks.append(
                {
                    "id": getattr(
                        duplicate,
                        "id",
                        None
                    ),
                    "title": getattr(
                        duplicate,
                        "title",
                        None
                    ),
                }
            )

            continue

        # ====================================================
        # CREATE NEW TASK
        # ====================================================

        task = Task(
            title=task_data.title,
            description=task_data.description,
            deadline=deadline,
            estimated_duration=(
                task_data.estimated_duration
            ),
            importance=task_data.importance
        )

        db.add(task)

        created_tasks.append(
            task
        )

    # ========================================================
    # 4. SAVE MEETINGS
    # ========================================================

    created_meetings = []

    for meeting_data in data.meetings:

        start_time = normalize_datetime(
            meeting_data.start_time,
            message_date
        )

        end_time = normalize_datetime(
            meeting_data.end_time,
            message_date
        )

        # ----------------------------------------------------
        # Validate meeting times
        # ----------------------------------------------------

        if (
            start_time is None
            or end_time is None
        ):
            continue

        if start_time >= end_time:
            continue

        participants = None

        if meeting_data.participants:

            participants = ", ".join(
                meeting_data.participants
            )

        meeting = Meeting(
            title=meeting_data.title,
            description=meeting_data.description,
            start_time=start_time,
            end_time=end_time,
            location=meeting_data.location,
            participants=participants
        )

        db.add(meeting)

        created_meetings.append(
            meeting
        )

    # ========================================================
    # 5. SAVE AVAILABILITY
    # ========================================================

    created_availability = []

    for availability_data in data.availability:

        # ----------------------------------------------------
        # Normalize dates
        # ----------------------------------------------------

        start_date = normalize_date(
            availability_data.start_date
        )

        end_date = normalize_date(
            availability_data.end_date
        )

        # ----------------------------------------------------
        # Normalize times
        # ----------------------------------------------------

        start_time = normalize_time(
            availability_data.start_time
        )

        end_time = normalize_time(
            availability_data.end_time
        )

        # ----------------------------------------------------
        # Extract weekdays from original message
        # ----------------------------------------------------

        message_weekdays = (
            weekdays_from_message(
                request.message
            )
        )

        # ----------------------------------------------------
        # Normalize model weekdays
        # ----------------------------------------------------

        weekdays = normalize_weekdays(
            availability_data.weekdays
        )

        # ----------------------------------------------------
        # Prefer deterministic weekdays
        # ----------------------------------------------------

        if message_weekdays:

            weekdays = ",".join(
                message_weekdays
            )

        # ----------------------------------------------------
        # Normalize recurrence
        # ----------------------------------------------------

        recurrence = normalize_recurrence(
            availability_data.recurrence,
            request.message,
            message_weekdays
            or availability_data.weekdays
        )

        # ----------------------------------------------------
        # FALLBACK START DATE
        # ----------------------------------------------------

        if start_date is None:

            start_date = message_date

        # ----------------------------------------------------
        # RECURRING AVAILABILITY
        # ----------------------------------------------------

        if recurrence in (
            "daily",
            "weekly",
        ):

            if end_date is None:

                end_date = (
                    start_date
                    + timedelta(
                        days=PLANNING_HORIZON_DAYS
                    )
                )

        # ----------------------------------------------------
        # NON-RECURRING AVAILABILITY
        # ----------------------------------------------------

        else:

            if end_date is None:
                end_date = start_date

            weekdays = None

        # ----------------------------------------------------
        # VALIDATE AVAILABILITY TIMES
        # ----------------------------------------------------

        if (
            start_time is None
            or end_time is None
        ):
            continue

        if start_time >= end_time:
            continue

        # ----------------------------------------------------
        # WEEKLY VALIDATION
        # ----------------------------------------------------

        if recurrence == "weekly":

            if not weekdays:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Weekly availability requires "
                        "at least one weekday."
                    )
                )

        # ----------------------------------------------------
        # DAILY AVAILABILITY
        # ----------------------------------------------------

        if recurrence == "daily":
            weekdays = None

        # ----------------------------------------------------
        # CREATE AVAILABILITY
        # ----------------------------------------------------

        availability = Availability(
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            recurrence=recurrence,
            weekdays=weekdays
        )

        db.add(availability)

        created_availability.append(
            availability
        )

    # ========================================================
    # 6. SAVE REMINDERS
    # ========================================================

    created_reminders = []

    # --------------------------------------------------------
    # First commit tasks, meetings and availability so that
    # generated database IDs are available.
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception as error:

        db.rollback()

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Database error: {error}"
            )
        )

    # --------------------------------------------------------
    # Refresh meetings
    # --------------------------------------------------------

    for meeting in created_meetings:

        db.refresh(
            meeting
        )

    # --------------------------------------------------------
    # Process parsed reminders
    # --------------------------------------------------------

    try:

        created_reminders = (
            process_reminders(
                db=db,

                reminders=[
                    reminder.model_dump()
                    for reminder
                    in data.reminders
                ],

                meetings=created_meetings
            )
        )

    except Exception as error:

        db.rollback()

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Reminder processing error: "
                f"{error}"
            )
        )

    # ========================================================
    # 7. COMMIT EVERYTHING
    # ========================================================

    try:

        db.commit()

    except Exception as error:

        db.rollback()

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Database error: {error}"
            )
        )

    # ========================================================
    # 8. REFRESH OBJECTS
    # ========================================================

    for task in created_tasks:
        db.refresh(task)

    for meeting in created_meetings:
        db.refresh(meeting)

    for availability in created_availability:
        db.refresh(availability)

    for reminder in created_reminders:
        db.refresh(reminder)

    # ========================================================
    # 9. RESPONSE
    # ========================================================

    return {
        "message": (
            "Message processed successfully"
        ),

        "command_processed": False,

        "extracted_data": (
            data.model_dump()
        ),

        "created": {
            "tasks": len(
                created_tasks
            ),

            "meetings": len(
                created_meetings
            ),

            "availability": len(
                created_availability
            ),

            "reminders": len(
                created_reminders
            )
        },

        "duplicates": {
            "tasks": duplicate_tasks
        }
    }