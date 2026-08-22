import json
import re
import subprocess
from pathlib import Path
from typing import Any




import os



PROJECT_ROOT = Path(__file__).resolve().parents[3]


LLAMA_CLI = Path(
    os.getenv(
        "LLAMA_CLI",
        str(
            PROJECT_ROOT
            / "llama.cpp"
            / "build"
            / "bin"
            / "Release"
            / "llama-cli.exe"
        ),
    )
)


MODEL_PATH = Path(
    os.getenv(
        "MODEL_PATH",
        str(
            PROJECT_ROOT
            / "models"
            / "gemma-3-1b-it-q4_0.gguf"
        ),
    )
)
SCHEMA_PATH = (
    PROJECT_ROOT
    / "management_schema.json"
)



CONTEXT_SIZE = "2048"
MAX_TOKENS = "256"
TIMEOUT = 120

GPU_DEVICE = "CUDA0"
GPU_LAYERS = "99"



SYSTEM_PROMPT = """
Extract information from the USER MESSAGE.

Return ONLY valid JSON with exactly:

{
  "tasks": [],
  "meetings": [],
  "availability": [],
  "reminders": []
}

Task:

{
  "title": string or null,
  "description": string or null,
  "deadline": string or null,
  "estimated_duration": integer or null,
  "importance": integer or null
}

Meeting:

{
  "title": string or null,
  "description": string or null,
  "start_time": string or null,
  "end_time": string or null,
  "location": string or null,
  "participants": array or null
}

Availability:

{
  "start_date": string or null,
  "end_date": string or null,
  "start_time": string or null,
  "end_time": string or null,
  "recurrence": "none" or "daily" or "weekly" or null,
  "weekdays": array or null
}

Reminder:

{
  "title": string or null,
  "message": string or null,
  "reminder_time": string or null,
  "reminder_type": string or null
}

Rules:

- Extract only what the user explicitly says.
- "2 hours" means 120 minutes.
- "3 PM" is a time.
- "tomorrow" is a date.
- "every day" means daily availability.
- "every Monday, Wednesday and Friday" means weekly availability.
- Do not explain anything.
- Do not return markdown.
- Do not return code fences.
- "next Monday" means the following Monday.
- "this Friday" means Friday in the current week.
- "tomorrow morning" means tomorrow at 09:00 AM.
- "tomorrow afternoon" means tomorrow at 02:00 PM.
- "tomorrow evening" means tomorrow at 06:00 PM.
- "tonight" means today at 08:00 PM.
- "this evening" means today at 06:00 PM.
"""



def check_files() -> None:
    """
    Validate the model file and, when configured, the llama.cpp CLI.

    Local Windows development can continue to use llama-cli.exe.
    Linux deployment can omit LLAMA_CLI and use llama-cpp-python.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Gemma model not found:\n{MODEL_PATH}"
        )

    if os.getenv("LLAMA_CLI") and not LLAMA_CLI.exists():
        raise FileNotFoundError(
            f"Configured llama CLI not found:\n{LLAMA_CLI}"
        )


def build_prompt(message: str) -> str:
    return (
        SYSTEM_PROMPT
        + "\nUSER MESSAGE:\n"
        + message.strip()
        + "\n\nJSON:"
    )



def extract_json(output: str) -> dict:
    output = output.strip()

    if not output:
        raise RuntimeError(
            "Gemma returned an empty response."
        )

    
    output = re.sub(
        r"```json",
        "",
        output,
        flags=re.IGNORECASE,
    )

    output = re.sub(
        r"```",
        "",
        output,
    )

    output = output.strip()

   
    start = output.find("{")

    if start == -1:
        raise ValueError(
            "No JSON object found in Gemma output."
        )

    decoder = json.JSONDecoder()

    try:
        data, _ = decoder.raw_decode(
            output[start:]
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON returned by Gemma: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            "Gemma JSON output must be an object."
        )

    return data



def normalize_lists(data: dict) -> dict:
    fields = [
        "tasks",
        "meetings",
        "availability",
        "reminders",
    ]

    for field in fields:

        if field not in data:
            data[field] = []

        elif data[field] is None:
            data[field] = []

        elif not isinstance(data[field], list):
            data[field] = []

    return data



def normalize_duration(
    value: Any,
) -> int | None:

    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, str):

        text = value.lower().strip()

        # "2 hours"
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*hours?",
            text,
        )

        if match:
            return int(
                float(match.group(1)) * 60
            )

        # "30 minutes"
        match = re.search(
            r"(\d+)\s*minutes?",
            text,
        )

        if match:
            return int(match.group(1))

        # Plain integer
        if text.isdigit():
            return int(text)

    return None



def duration_from_message(
    message: str,
) -> int | None:

    text = message.lower()

    word_hours = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }

    
    for word, number in word_hours.items():

        pattern = rf"\b{word}\s+hours?\b"

        if re.search(
            pattern,
            text,
        ):
            return number * 60

    
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*hours?\b",
        text,
    )

    if match:
        return int(
            float(match.group(1)) * 60
        )

   
    match = re.search(
        r"\b(\d+)\s*minutes?\b",
        text,
    )

    if match:
        return int(match.group(1))

    return None



def importance_from_message(
    message: str,
) -> int | None:

    text = message.lower()

    
    if any(
        phrase in text
        for phrase in [
            "extremely important",
            "critically important",
            "critical",
            "urgent",
        ]
    ):
        return 5

    
    if any(
        phrase in text
        for phrase in [
            "very important",
            "high priority",
            "high-priority",
        ]
    ):
        return 4

   
    if "important" in text:
        return 4

   
    if any(
        phrase in text
        for phrase in [
            "low priority",
            "low-priority",
            "not important",
        ]
    ):
        return 1

    return None



WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

TIME_PERIOD_DEFAULTS = {
    "morning": "09:00 AM",
    "afternoon": "02:00 PM",
    "evening": "06:00 PM",
    "tonight": "08:00 PM",
}


def get_next_weekday(
    weekday_name: str,
):
    """
    Return the weekday in the following week.

    Examples for Thursday, August 20, 2026:

        next Monday -> 2026-08-24
        next Friday -> 2026-08-28

    "this Friday" is handled separately by
    get_this_weekday().
    """

    from datetime import date, timedelta

    weekday_name = (
        weekday_name
        .strip()
        .lower()
    )

    target_weekday = WEEKDAY_NAMES.get(
        weekday_name
    )

    if target_weekday is None:
        return None

    today = date.today()

    # Start of the current week (Monday)
    current_week_start = (
        today
        - timedelta(
            days=today.weekday()
        )
    )

    # Start of the following week
    next_week_start = (
        current_week_start
        + timedelta(days=7)
    )

    return (
        next_week_start
        + timedelta(
            days=target_weekday
        )
    )

def get_this_weekday(
    weekday_name: str,
):
    """
    Return the closest occurrence of a weekday
    within the current week.

    Monday is considered the first day
    of the week.
    """

    from datetime import date, timedelta

    weekday_name = (
        weekday_name
        .strip()
        .lower()
    )

    target_weekday = WEEKDAY_NAMES.get(
        weekday_name
    )

    if target_weekday is None:
        return None

    today = date.today()

    current_week_start = (
        today
        - timedelta(
            days=today.weekday()
        )
    )

    return (
        current_week_start
        + timedelta(
            days=target_weekday
        )
    )


def relative_weekday_from_message(
    message: str,
):
    """
    Detect phrases such as:

        next Monday
        next Friday
        this Monday
        this Friday

    Returns an ISO date string when found.
    """

    text = message.lower()

    
    match = re.search(
        r"\bnext\s+"
        r"(monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
        text,
        re.IGNORECASE,
    )

    if match:

        target = get_next_weekday(
            match.group(1)
        )

        if target is not None:
            return target.isoformat()

    
    match = re.search(
        r"\bthis\s+"
        r"(monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
        text,
        re.IGNORECASE,
    )

    if match:

        target = get_this_weekday(
            match.group(1)
        )

        if target is not None:
            return target.isoformat()

    return None


def time_period_from_message(
    message: str,
):
    """
    Detect natural-language time periods.

    Examples:

        tomorrow morning
        tomorrow afternoon
        tomorrow evening
        tonight
        this evening
    """

    text = message.lower()

   
    if re.search(
        r"\btonight\b",
        text,
        re.IGNORECASE,
    ):
        return {
            "period": "tonight",
            "time": TIME_PERIOD_DEFAULTS["tonight"],
        }

    
    for period in [
        "morning",
        "afternoon",
        "evening",
    ]:

        if re.search(
            rf"\b{period}\b",
            text,
            re.IGNORECASE,
        ):
            return {
                "period": period,
                "time": TIME_PERIOD_DEFAULTS[period],
            }

    return None



def relative_datetime_from_message(
    message: str,
):
    """
    Resolve phrases such as:

        tomorrow morning
        tomorrow afternoon
        tomorrow evening
        tonight
        this evening
    """

    from datetime import date, timedelta

    text = message.lower()

    period_data = time_period_from_message(
        message
    )

    if period_data is None:
        return None

    
    target_date = None

    if "tomorrow" in text:

        target_date = (
            date.today()
            + timedelta(days=1)
        )

    elif "today" in text:

        target_date = date.today()

    elif "tonight" in text:

        target_date = date.today()

    else:

        relative_weekday = (
            relative_weekday_from_message(
                message
            )
        )

        if relative_weekday is not None:
            target_date = date.fromisoformat(
                relative_weekday
            )

    if target_date is None:
        return None

    return (
        f"{target_date.isoformat()} "
        f"{period_data['time']}"
    )


def deadline_from_message(
    message: str,
) -> str | None:
    """
    Determine an explicitly mentioned task deadline.

    Supports:

        today
        tomorrow
        yesterday
        next Monday
        next Friday
        this Monday
        this Friday
        tomorrow morning
        tomorrow afternoon
        tomorrow evening
        tonight
        this evening
    """

    text = message.lower()

   
    relative_datetime = (
        relative_datetime_from_message(
            message
        )
    )

    if relative_datetime is not None:
        return relative_datetime

    
    relative_weekday = (
        relative_weekday_from_message(
            message
        )
    )

    if relative_weekday is not None:
        return relative_weekday

   
    if "tomorrow" in text:
        return "tomorrow"

    if "today" in text:
        return "today"

    if "yesterday" in text:
        return "yesterday"

    return None


def task_title_from_message(
    message: str,
) -> str | None:
    """
    Extract a task title from natural language.

    Examples:
        finish my AI assignment next Monday
        I need an E2E AI Python assignment tomorrow
        I need to finish my Python assignment tomorrow
        complete Python project tomorrow
        study machine learning today

    Date/time and supporting clauses are removed from the title.
    """

    text = message.strip()

   
    # Common temporal/supporting phrases that should never become
    # part of the task title.
    
    stop_phrase = (
        r"(?=\s+(?:"
        r"today|tomorrow|yesterday|"
        r"this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"by\s+(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"due\s+(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"it\s+will\s+take\b|"
        r"it\s+takes\b|"
        r"and\s+(?:it\s+is|it's)\b"
        r")"
        r"|[.!?]|$)"
    )

    patterns = [
        # "I need an E2E AI Python assignment tomorrow"
        r"\b(?:i\s+)?need\s+"
        r"(?:a|an|the|my)\s+"
        r"(.+?)"
        + stop_phrase,

        # "I have an E2E AI Python assignment tomorrow"
        r"\b(?:i\s+)?have\s+"
        r"(?:a|an|the|my)\s+"
        r"(.+?)"
        + stop_phrase,

        # "I want an E2E AI Python assignment tomorrow"
        r"\b(?:i\s+)?want\s+"
        r"(?:a|an|the|my)\s+"
        r"(.+?)"
        + stop_phrase,

        # "I need to finish my E2E AI Python assignment tomorrow"
        r"\b(?:i\s+)?(?:need|have|want|plan|intend)\s+to\s+"
        r"(?:finish|complete|do|work\s+on|study|prepare|submit)\s+"
        r"(?:my|the|a|an)?\s*"
        r"(.+?)"
        + stop_phrase,

        # "finish my AI assignment next Monday"
        r"\b(?:finish|complete|do|work\s+on|study|prepare|submit)\s+"
        r"(?:my|the|a|an)?\s*"
        r"(.+?)"
        + stop_phrase,

        # "assignment: AI assignment"
        r"(?:assignment|project|task)"
        r"\s*[:\-]\s*"
        r"(.+?)"
        r"(?:[.!?]|$)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            continue

        title = match.group(1).strip()

        
        # Remove common filler
      
        title = re.sub(
            r"^(?:called|named)\s+",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"\s+it\s+will\s+take.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"\s+it\s+takes.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"\s+and\s+(?:it\s+is|it's)\s+.*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = title.rstrip(".,!? ").strip()

       
        # Reject temporal/filler-only titles.
        
        invalid_titles = {
            "today",
            "tomorrow",
            "yesterday",
            "morning",
            "afternoon",
            "evening",
            "tonight",
            "important",
            "very important",
            "high priority",
            "critical",
            "urgent",
        }

        if title.lower() in invalid_titles:
            continue

        if title:
            return title

    return None



def clean_tasks(
    data: dict,
    original_message: str,
) -> dict:

    cleaned = []

    original_duration = (
        duration_from_message(
            original_message
        )
    )

    original_importance = (
        importance_from_message(
            original_message
        )
    )

    original_deadline = (
        deadline_from_message(
            original_message
        )
    )

    for task in data["tasks"]:

        if not isinstance(
            task,
            dict,
        ):
            continue

        duration = normalize_duration(
            task.get(
                "estimated_duration"
            )
        )

        if original_duration is not None:
            duration = original_duration

        importance = task.get(
            "importance"
        )

        if not isinstance(
            importance,
            int,
        ):
            importance = None

        if not (
            importance is None
            or 1 <= importance <= 5
        ):
            importance = None

        if original_importance is not None:
            importance = original_importance

        deadline = task.get(
            "deadline"
        )

        if original_deadline is not None:
            deadline = original_deadline

        ai_title = task.get("title")

        # Reject temporal-only AI titles; deterministic correction later
        # will recover the real title from the user message.
        if isinstance(ai_title, str):
            if ai_title.strip().lower() in {
                "today",
                "tomorrow",
                "yesterday",
                "morning",
                "afternoon",
                "evening",
                "tonight",
            }:
                ai_title = None

        cleaned.append(
            {
                "title": ai_title,
                "description": task.get(
                    "description"
                ),
                "deadline": deadline,
                "estimated_duration": duration,
                "importance": importance,
            }
        )

    data["tasks"] = cleaned

    return data



def fix_task_from_message(
    data: dict,
    message: str,
) -> dict:

    title = task_title_from_message(
        message
    )

    duration = duration_from_message(
        message
    )

    importance = importance_from_message(
        message
    )

    deadline = deadline_from_message(
        message
    )

    # If the original message contains a valid deterministic task title,
    # use it even when Gemma returned a bad title such as "tomorrow".
    if not title:
        return data

   
    for task in data["tasks"]:

        if not isinstance(
            task,
            dict,
        ):
            continue

        existing_title = task.get(
            "title"
        )

        # Replace obviously invalid AI titles with the deterministic
        # title recovered from the original user message.
        invalid_ai_title = (
            not existing_title
            or str(existing_title).strip().lower()
            in {
                "today",
                "tomorrow",
                "yesterday",
                "morning",
                "afternoon",
                "evening",
                "tonight",
            }
        )

        if invalid_ai_title:
            task["title"] = title
            existing_title = title

        existing_text = (
            str(existing_title)
            .lower()
        )

        title_text = title.lower()

        if (
            title_text in existing_text
            or existing_text in title_text
        ):

            if duration is not None:
                task[
                    "estimated_duration"
                ] = duration

            if importance is not None:
                task["importance"] = (
                    importance
                )

            if deadline is not None:
                task["deadline"] = deadline

            return data

   
    data["tasks"].append(
        {
            "title": title,
            "description": None,
            "deadline": deadline,
            "estimated_duration": duration,
            "importance": importance,
        }
    )

    return data



def clean_meetings(
    data: dict,
) -> dict:
    cleaned = []

    for meeting in data["meetings"]:

        if not isinstance(
            meeting,
            dict,
        ):
            continue

        start_time = meeting.get(
            "start_time"
        )

        end_time = meeting.get(
            "end_time"
        )

        
        if not start_time or not end_time:
            continue

       
        if (
            isinstance(start_time, str)
            and re.fullmatch(
                r"\d{3,4}",
                start_time.strip(),
            )
        ):
            continue

        if (
            isinstance(end_time, str)
            and re.fullmatch(
                r"\d{3,4}",
                end_time.strip(),
            )
        ):
            continue

        participants = meeting.get(
            "participants"
        )

        if participants is not None:

            if not isinstance(
                participants,
                list,
            ):
                participants = []

            participants = [
                str(person).strip()
                for person in participants
                if str(person).strip()
            ]

        cleaned.append(
            {
                "title": (
                    meeting.get(
                        "title"
                    )
                    or "Meeting"
                ),

                "description": (
                    meeting.get(
                        "description"
                    )
                ),

                "start_time": (
                    start_time
                ),

                "end_time": (
                    end_time
                ),

                "location": (
                    meeting.get(
                        "location"
                    )
                ),

                "participants": (
                    participants
                ),
            }
        )

    data["meetings"] = cleaned

    return data



def clean_availability(
    data: dict,
) -> dict:

    cleaned = []

    valid_recurrence = {
        "none",
        "daily",
        "weekly",
    }

    valid_weekdays = {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }

    for availability in data[
        "availability"
    ]:

        if not isinstance(
            availability,
            dict,
        ):
            continue

        recurrence = availability.get(
            "recurrence"
        )

        if recurrence not in valid_recurrence:
            recurrence = None

        weekdays = availability.get(
            "weekdays"
        )

        if weekdays is not None:

            if not isinstance(
                weekdays,
                list,
            ):
                weekdays = []

            cleaned_weekdays = []

            for day in weekdays:

                if not isinstance(
                    day,
                    str,
                ):
                    continue

                day = day.strip()

                # Normalize capitalization
                day = day.capitalize()

                if day in valid_weekdays:
                    cleaned_weekdays.append(
                        day
                    )

            weekdays = cleaned_weekdays

        cleaned.append(
            {
                "start_date": availability.get(
                    "start_date"
                ),
                "end_date": availability.get(
                    "end_date"
                ),
                "start_time": availability.get(
                    "start_time"
                ),
                "end_time": availability.get(
                    "end_time"
                ),
                "recurrence": recurrence,
                "weekdays": weekdays,
            }
        )

    data["availability"] = cleaned

    return data



def normalize_time(
    value: str,
) -> str:

    if value is None:
        return value

    value = value.strip().upper()

    
    match = re.match(
        r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)",
        value,
    )

    if match:

        hour = int(
            match.group(1)
        )

        minute = (
            match.group(2)
            if match.group(2)
            else "00"
        )

        period = match.group(3)

        return (
            f"{hour}:{minute} {period}"
        )

    return value



def fix_meeting_from_message(
    data: dict,
    message: str,
) -> dict:
    """
    Deterministically extract meeting date/time
    from each meeting phrase.

    Supports:

        meeting tomorrow from 3 PM to 4 PM
        meeting next Monday from 3 PM to 4 PM
        meeting this Friday from 10 AM to 11 AM
    """

   
    meeting_pattern = re.compile(
        r"(?:"
        r"(?:I\s+have|I\s+have\s+a|"
        r"there\s+is|schedule|"
        r"set\s+up|book)\s+)?"
        r"(?:a\s+)?"
        r"meeting"
        r"(?:\s+(?P<date_phrase>"
        r"tomorrow|today|yesterday|"
        r"next\s+(?:monday|tuesday|wednesday|"
        r"thursday|friday|saturday|sunday)|"
        r"this\s+(?:monday|tuesday|wednesday|"
        r"thursday|friday|saturday|sunday)"
        r"))?"
        r"\s+from\s+"
        r"(?P<start>"
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)"
        r")"
        r"\s+to\s+"
        r"(?P<end>"
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)"
        r")",
        re.IGNORECASE,
    )

    matches = list(
        meeting_pattern.finditer(
            message
        )
    )

    if not matches:
        return data

    
    for index, match in enumerate(
        matches
    ):

        date_phrase = (
            match.group("date_phrase")
        )

        start_time = normalize_time(
            match.group("start")
        )

        end_time = normalize_time(
            match.group("end")
        )

       
        resolved_date = None

        if date_phrase:

            date_phrase_lower = (
                date_phrase.lower()
            )

          
            if (
                date_phrase_lower.startswith(
                    "next "
                )
                or date_phrase_lower.startswith(
                    "this "
                )
            ):

                resolved_date = (
                    relative_weekday_from_message(
                        date_phrase
                    )
                )

           
            elif date_phrase_lower == "today":

                from datetime import date

                resolved_date = (
                    date.today().isoformat()
                )

            elif (
                date_phrase_lower
                == "tomorrow"
            ):

                from datetime import (
                    date,
                    timedelta,
                )

                resolved_date = (
                    date.today()
                    + timedelta(days=1)
                ).isoformat()

            elif (
                date_phrase_lower
                == "yesterday"
            ):

                from datetime import (
                    date,
                    timedelta,
                )

                resolved_date = (
                    date.today()
                    - timedelta(days=1)
                ).isoformat()

        
        if resolved_date:

            start_datetime = (
                f"{resolved_date} "
                f"{start_time}"
            )

            end_datetime = (
                f"{resolved_date} "
                f"{end_time}"
            )

        else:

            start_datetime = start_time
            end_datetime = end_time

       
        meeting = None

        if index < len(data["meetings"]):

            candidate = (
                data["meetings"][index]
            )

            if isinstance(
                candidate,
                dict,
            ):
                meeting = candidate

       
        if meeting is not None:

            meeting["start_time"] = (
                start_datetime
            )

            meeting["end_time"] = (
                end_datetime
            )

            if not meeting.get(
                "title"
            ):
                meeting["title"] = (
                    "Meeting"
                )

        
        else:

            data["meetings"].append(
                {
                    "title": "Meeting",
                    "description": None,
                    "start_time": (
                        start_datetime
                    ),
                    "end_time": (
                        end_datetime
                    ),
                    "location": None,
                    "participants": None,
                }
            )

    return data


def weekdays_from_message(
    message: str,
):
    """
    Extract explicitly mentioned weekdays.

    Supports:

        Monday, Wednesday and Friday

        every Monday Wednesday Friday

        Monday to Friday

        Monday through Friday
    """

    text = message.lower()

    weekday_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

 
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

 
    found = []

    for day in weekday_order:

        if day.lower() in text:

            found.append(day)

    if not found:
        return None

    return found



def fix_availability_from_message(
    data: dict,
    message: str,
) -> dict:
    """
    Deterministically extract availability.

    Examples:

        I am free from 5 PM to 9 PM.

        I am free tomorrow from 2 PM to 4 PM.

        I am free every Monday, Wednesday and Friday
        from 6 PM to 9 PM.

        I am available Monday to Friday
        from 9 AM to 5 PM.
    """

    text = message.lower().strip()

 
    match = re.search(
        r"(?:free|available)\s+"
        r"(?:every\s+)?"
        r"(?:[a-z,\s]+?\s+)?"
        r"from\s+"
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))"
        r"\s+to\s+"
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))",
        text,
        re.IGNORECASE,
    )

    if not match:
        return data

    start_time = normalize_time(
        match.group(1)
    )

    end_time = normalize_time(
        match.group(2)
    )

 
    weekdays = weekdays_from_message(
        message
    )


    is_weekly = bool(
        weekdays
    ) or any(
        phrase in text
        for phrase in [
            "every week",
            "each week",
            "weekly",
        ]
    )

 
    has_tomorrow = (
        "tomorrow" in text
    )

    has_today = (
        "today" in text
    )

  
    if is_weekly:

        availability_data = {
            "start_date": (
                "tomorrow"
                if has_tomorrow
                else "today"
                if has_today
                else None
            ),
            "end_date": (
                "tomorrow"
                if has_tomorrow
                else "today"
                if has_today
                else None
            ),
            "start_time": start_time,
            "end_time": end_time,
            "recurrence": "weekly",
            "weekdays": weekdays,
        }

        if data["availability"]:

            existing = data[
                "availability"
            ][0]

            existing.update(
                availability_data
            )

        else:

            data["availability"].append(
                availability_data
            )

        return data

   
    availability_data = {
        "start_date": (
            "tomorrow"
            if has_tomorrow
            else "today"
            if has_today
            else None
        ),
        "end_date": (
            "tomorrow"
            if has_tomorrow
            else "today"
            if has_today
            else None
        ),
        "start_time": start_time,
        "end_time": end_time,
        "recurrence": "none",
        "weekdays": None,
    }

    if data["availability"]:

        existing = data[
            "availability"
        ][0]

        existing.update(
            availability_data
        )

    else:

        data["availability"].append(
            availability_data
        )

    return data



def clean_reminders(
    data: dict,
) -> dict:

    cleaned = []

    valid_types = {
        "before_event",
        "at_time",
        "after_event",
    }

    for reminder in data[
        "reminders"
    ]:

        if not isinstance(
            reminder,
            dict,
        ):
            continue

        reminder_type = reminder.get(
            "reminder_type"
        )

        if reminder_type not in valid_types:
            reminder_type = None

        cleaned.append(
            {
                "title": reminder.get(
                    "title"
                ),
                "message": reminder.get(
                    "message"
                ),
                "reminder_time": reminder.get(
                    "reminder_time"
                ),
                "reminder_type": reminder_type,
            }
        )

    data["reminders"] = cleaned

    return data



def fix_reminder_from_message(
    data: dict,
    message: str,
) -> dict:

    text = message.lower()

    if "remind me" not in text:
        return data

 
    if "before" in text:

        if not data["reminders"]:

            data["reminders"].append(
                {
                    "title": "Reminder",
                    "message": message.strip(),
                    "reminder_time": None,
                    "reminder_type": "before_event",
                }
            )

        else:

            for reminder in data[
                "reminders"
            ]:

                if not isinstance(
                    reminder,
                    dict,
                ):
                    continue

                reminder[
                    "reminder_type"
                ] = "before_event"

                if not reminder.get(
                    "message"
                ):
                    reminder[
                        "message"
                    ] = message.strip()

  
    elif "after" in text:

        for reminder in data[
            "reminders"
        ]:

            if isinstance(
                reminder,
                dict,
            ):

                reminder[
                    "reminder_type"
                ] = "after_event"

    return data



def clean_result(
    data: dict,
    original_message: str,
) -> dict:

    data = normalize_lists(
        data
    )

    data = clean_tasks(
        data,
        original_message,
    )

    data = clean_meetings(
        data
    )

    data = clean_availability(
        data
    )

    data = clean_reminders(
        data
    )

  
    data = fix_meeting_from_message(
        data,
        original_message,
    )

    data = fix_availability_from_message(
        data,
        original_message,
    )

    data = fix_task_from_message(
        data,
        original_message,
    )

    data = fix_reminder_from_message(
        data,
        original_message,
    )

    return data


 
def run_gemma(prompt: str) -> str:
    """
    Run Gemma using the available runtime.

    Windows/local:
        existing llama.cpp CLI.

    Linux/Render:
        llama-cpp-python CPU fallback when LLAMA_CLI is not available.
    """

    # Existing llama.cpp CLI path.
    if LLAMA_CLI.exists():
        command = [
            str(LLAMA_CLI),
            "-m",
            str(MODEL_PATH),
            "-ngl",
            GPU_LAYERS,
            "--device",
            GPU_DEVICE,
            "-c",
            CONTEXT_SIZE,
            "-n",
            MAX_TOKENS,
            "--temp",
            "0",
            "--single-turn",
            "-p",
            prompt,
        ]

        print("\n========== GEMMA REQUEST ==========")
        print("Runtime: llama.cpp CLI")
        print(f"Device: {GPU_DEVICE}")
        print(f"GPU layers: {GPU_LAYERS}")
        print(f"Context: {CONTEXT_SIZE}")
        print(f"Max tokens: {MAX_TOKENS}")
        print(f"Timeout: {TIMEOUT}")
        print("Conversation mode: SINGLE-TURN")
        print("JSON grammar: DISABLED")
        print("===================================\n")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"Gemma model timed out after {TIMEOUT} seconds."
            ) from error
        except Exception as error:
            raise RuntimeError(
                f"Failed to run Gemma CLI: "
                f"{type(error).__name__}: {error}"
            ) from error

        if result.returncode != 0:
            print("\n========== GEMMA ERROR ==========")
            print(result.stderr)
            print("=================================\n")
            raise RuntimeError(
                f"Gemma CLI failed:\n{result.stderr}"
            )

        return result.stdout.strip()

    # Linux/CPU fallback.
    import importlib

    try:
        llama_cpp = importlib.import_module("llama_cpp")
        Llama = llama_cpp.Llama
    except ImportError as error:
        raise RuntimeError(
            "No supported Gemma runtime is available. "
            "Local Windows uses LLAMA_CLI; Linux deployment "
            "requires llama-cpp-python."
        ) from error

    print("\n========== GEMMA REQUEST ==========")
    print("Runtime: llama-cpp-python")
    print("Device: CPU")
    print(f"Context: {CONTEXT_SIZE}")
    print(f"Max tokens: {MAX_TOKENS}")
    print(f"Timeout: {TIMEOUT}")
    print("===================================\n")

    try:
        model = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=int(CONTEXT_SIZE),
            n_gpu_layers=0,
            verbose=False,
        )

        response = model(
            prompt,
            max_tokens=int(MAX_TOKENS),
            temperature=0,
        )

        choices = response.get("choices", [])
        if not choices:
            raise RuntimeError(
                "llama-cpp-python returned no choices."
            )

        output = choices[0].get("text", "")
        if not output.strip():
            raise RuntimeError(
                "llama-cpp-python returned an empty response."
            )

        return output.strip()

    except Exception as error:
        raise RuntimeError(
            f"Failed to run Gemma with llama-cpp-python: "
            f"{type(error).__name__}: {error}"
        ) from error


def extract_information(
    message: str,
) -> dict:

    if not message or not message.strip():
        raise ValueError(
            "Message cannot be empty."
        )

    check_files()

    prompt = build_prompt(
        message
    )

    output = run_gemma(prompt)


    print(
        "\n========== GEMMA RAW OUTPUT =========="
    )

    print(
        output
    )

    print(
        "=======================================\n"
    )

  
    try:

        data = extract_json(
            output
        )

    except Exception as error:

        print(
            "\n========== JSON ERROR =========="
        )

        print(
            error
        )

        print(
            "Raw output:"
        )

        print(
            output
        )

        print(
            "================================\n"
        )

        raise RuntimeError(
            "Could not parse Gemma output "
            f"as JSON: {error}"
        ) from error

  
    data = clean_result(
        data,
        message,
    )

  
    print(
        "\n========== FINAL PARSED DATA =========="
    )

    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        "=======================================\n"
    )

    return data



if __name__ == "__main__":

    message = (
        "I need to finish my AI assignment "
        "tomorrow morning. "
        "It will take two hours and it is very important. "
        "I have a meeting next Friday from 3 PM to 4 PM."
    )

    try:

        result = extract_information(
            message
        )

        print(
            "\n========== FINAL RESULT =========="
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        print(
            "=================================="
        )

    except Exception as error:

        print(
            "\n========== PARSER ERROR =========="
        )

        print(
            type(error).__name__
        )

        print(
            error
        )

        print(
            "=================================="
        )