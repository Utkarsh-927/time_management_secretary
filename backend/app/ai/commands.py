import re
from typing import Any




COMMAND_NONE = "none"

COMMAND_UPDATE_TASK = "update_task"
COMMAND_DELETE_TASK = "delete_task"

COMMAND_UPDATE_MEETING = "update_meeting"
COMMAND_DELETE_MEETING = "delete_meeting"

COMMAND_CREATE_REMINDER = "create_reminder"




WEEKDAY_PATTERN = (
    r"monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday"
)



def clean_title(value: str | None):
    """
    Clean a task or meeting title extracted
    from a natural-language command.
    """

    if value is None:
        return None

    value = value.strip()

    value = re.sub(
        r"^(?:my|the)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s+(?:task|meeting)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.rstrip(
        ".,!?"
    )

    return value.strip() or None



def importance_from_command(
    message: str,
):
    """
    Convert natural-language priority into
    the Task importance scale 1-5.
    """

    text = message.lower()

 
    if any(
        phrase in text
        for phrase in [
            "critical",
            "extremely important",
            "critically important",
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

 
    if any(
        phrase in text
        for phrase in [
            "normal priority",
            "medium priority",
            "medium-priority",
        ]
    ):
        return 3

  
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



def extract_task_title(
    message: str,
    command_type: str | None = None,
):
    """
    Extract a task title from commands such as:

        Move my ML assignment to Friday.
        Move the Python task to tomorrow.
        Cancel my Python task.
        Make Python task high priority.
        Make my Python task critical.
    """

    text = message.strip()

   
    match = re.search(
        r"\b(?:move|reschedule|shift)"
        r"\s+(?:my|the)\s+"
        r"(.+?)"
        r"\s+to\s+"
        r"(?:"
        r"today|"
        r"tomorrow|"
        r"yesterday|"
        r"(?:this|next)\s+"
        r"(?:"
        + WEEKDAY_PATTERN
        + r")|"
        r"(?:"
        + WEEKDAY_PATTERN
        + r")"
        r")"
        r"\s*[.!]?$",
        text,
        re.IGNORECASE,
    )

    if match:

        title = match.group(1).strip()

        title = re.sub(
            r"\s+task$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        return clean_title(
            title
        )

 
    match = re.search(
        r"\b(?:cancel|delete|remove|drop)"
        r"\s+(?:my|the)\s+"
        r"(.+?)"
        r"\s+task\b",
        text,
        re.IGNORECASE,
    )

    if match:

        return clean_title(
            match.group(1)
        )

 
    importance = importance_from_command(
        message
    )

    if importance is not None:

     
        match = re.search(
            r"\b(?:make|set|change)"
            r"\s+(?:my|the)\s+"
            r"(.+?)"
            r"\s+task"
            r"\s+(?:to\s+)?"
            r"(?:"
            r"critical|"
            r"extremely\s+important|"
            r"critically\s+important|"
            r"very\s+important|"
            r"high[\s-]+priority|"
            r"important|"
            r"normal[\s-]+priority|"
            r"medium[\s-]+priority|"
            r"low[\s-]+priority|"
            r"not\s+important"
            r")"
            r"\s*[.!]?$",
            text,
            re.IGNORECASE,
        )

        if match:

            return clean_title(
                match.group(1)
            )

     
        match = re.search(
            r"\b(?:make|set|change)"
            r"\s+"
            r"(.+?)"
            r"\s+task"
            r"\s+(?:to\s+)?"
            r"(?:"
            r"critical|"
            r"extremely\s+important|"
            r"critically\s+important|"
            r"very\s+important|"
            r"high[\s-]+priority|"
            r"important|"
            r"normal[\s-]+priority|"
            r"medium[\s-]+priority|"
            r"low[\s-]+priority|"
            r"not\s+important"
            r")"
            r"\s*[.!]?$",
            text,
            re.IGNORECASE,
        )

        if match:

            return clean_title(
                match.group(1)
            )

    return None



def extract_meeting_title(
    message: str,
):
    """
    Extract meeting title from commands.

    Examples:

        Cancel tomorrow's meeting.
        Move my team meeting to Friday.
    """

    text = message.strip()

  
    match = re.search(
        r"\b(?:my|the)\s+"
        r"(.+?)\s+meeting\b",
        text,
        re.IGNORECASE,
    )

    if match:

        title = match.group(1).strip()

        return clean_title(
            title
        )

 
    if re.search(
        r"\bmeeting\b",
        text,
        re.IGNORECASE,
    ):
        return "Meeting"

    return None



def extract_relative_date(
    message: str,
):
    """
    Extract destination date phrases.

    Supports:

        today
        tomorrow
        yesterday
        Friday
        next Friday
        this Friday
    """

    patterns = [
       
        (
            rf"\b(?:next|this)\s+"
            rf"(?:{WEEKDAY_PATTERN})\b"
        ),

    
        (
            rf"\b(?:{WEEKDAY_PATTERN})\b"
        ),

    
        r"\b(?:today|tomorrow|yesterday)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            message,
            re.IGNORECASE,
        )

        if match:

            return match.group(
                0
            ).strip()

    return None



def detect_task_command(
    message: str,
):
    """
    Detect task modification commands.
    """

    text = message.lower().strip()


    if (
        re.search(
            r"\b(?:cancel|delete|remove|drop)\b",
            text,
        )
        and re.search(
            r"\btask\b",
            text,
        )
    ):

        return {
            "intent": COMMAND_DELETE_TASK,

            "task_title": (
                extract_task_title(
                    message,
                    COMMAND_DELETE_TASK,
                )
            ),

            "changes": {},
        }


    if (
        re.search(
            r"\b(?:make|set|change)\b",
            text,
        )
        and re.search(
            r"\b(?:priority|important|importance|"
            r"critical|high-priority|low-priority|"
            r"medium-priority)\b",
            text,
        )
    ):

        importance = importance_from_command(
            message
        )

        if importance is not None:

            task_title = (
                extract_task_title(
                    message,
                    COMMAND_UPDATE_TASK,
                )
            )

            return {
                "intent": COMMAND_UPDATE_TASK,

                "task_title": task_title,

                "changes": {
                    "importance": importance,
                },
            }


    if (
        re.search(
            r"\b(?:move|reschedule|shift)\b",
            text,
        )
        and re.search(
            r"\bto\b",
            text,
        )
    ):

        destination = (
            extract_relative_date(
                message
            )
        )

        if destination is not None:

            task_title = (
                extract_task_title(
                    message,
                    COMMAND_UPDATE_TASK,
                )
            )

            return {
                "intent": COMMAND_UPDATE_TASK,

                "task_title": task_title,

                "changes": {
                    "deadline_phrase": (
                        destination
                    ),
                },
            }

    return None


def detect_meeting_command(
    message: str,
):
    """
    Detect meeting modification commands.
    """

    text = message.lower().strip()

    if not re.search(
        r"\bmeeting\b",
        text,
    ):
        return None

 
    if re.search(
        r"\b(?:cancel|delete|remove)\b",
        text,
    ):

        return {
            "intent": COMMAND_DELETE_MEETING,

            "meeting_title": (
                extract_meeting_title(
                    message
                )
            ),

            "changes": {},
        }

   
    if re.search(
        r"\b(?:move|reschedule|shift|change)\b",
        text,
    ):

        destination = (
            extract_relative_date(
                message
            )
        )

        return {
            "intent": COMMAND_UPDATE_MEETING,

            "meeting_title": (
                extract_meeting_title(
                    message
                )
            ),

            "changes": {
                "date_phrase": (
                    destination
                ),
            },
        }

    return None



def detect_reminder_command(
    message: str,
):
    """
    Detect commands such as:

        Remind me 1 hour before the meeting.
        Remind me 30 minutes before my meeting.
    """

    text = message.lower().strip()

    if "remind me" not in text:
        return None


    hour_match = re.search(
        r"(\d+(?:\.\d+)?)"
        r"\s*hours?"
        r"\s*before",
        text,
        re.IGNORECASE,
    )

    if hour_match:

        minutes = int(
            float(
                hour_match.group(1)
            ) * 60
        )

        return {
            "intent": COMMAND_CREATE_REMINDER,

            "minutes_before": minutes,

            "target": (
                "meeting"
                if "meeting" in text
                else "event"
            ),

            "message": message.strip(),
        }

 
    minute_match = re.search(
        r"(\d+)"
        r"\s*minutes?"
        r"\s*before",
        text,
        re.IGNORECASE,
    )

    if minute_match:

        minutes = int(
            minute_match.group(1)
        )

        return {
            "intent": COMMAND_CREATE_REMINDER,

            "minutes_before": minutes,

            "target": (
                "meeting"
                if "meeting" in text
                else "event"
            ),

            "message": message.strip(),
        }

    return None



def detect_command(
    message: str,
) -> dict[str, Any]:
    """
    Detect whether a user message is a
    management modification command.

    Priority:

        1. Reminder
        2. Meeting command
        3. Task command
        4. None
    """

    if not message or not message.strip():

        return {
            "intent": COMMAND_NONE
        }

    reminder_command = (
        detect_reminder_command(
            message
        )
    )

    if reminder_command is not None:
        return reminder_command


    meeting_command = (
        detect_meeting_command(
            message
        )
    )

    if meeting_command is not None:
        return meeting_command

 
    task_command = (
        detect_task_command(
            message
        )
    )

    if task_command is not None:
        return task_command

  
    return {
        "intent": COMMAND_NONE
    }



if __name__ == "__main__":

    test_messages = [
        "Move my ML assignment to Friday.",
        "Move my ML assignment to next Monday.",
        "Move the Python task to tomorrow.",
        "Cancel my Python task.",
        "Delete the ML assignment task.",
        "Make Python task high priority.",
        "Make my Python task critical.",
        "Set Python task to low priority.",
        "Cancel tomorrow's meeting.",
        "Move my team meeting to Friday.",
        "Move my team meeting to next Monday.",
        "Remind me 1 hour before the meeting.",
        "Remind me 30 minutes before my meeting.",
        "I need an ML assignment tomorrow.",
    ]

    print(
        "\n========== COMMAND TESTS ==========\n"
    )

    for message in test_messages:

        result = detect_command(
            message
        )

        print(
            f"Message: {message}"
        )

        print(
            f"Result:  {result}"
        )

        print(
            "-" * 70
        )