from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta
from typing import Any, Optional




DEFAULT_LLAMA_CLI = (
    r"D:\Management_model\llama.cpp\build\bin\Release\llama-cli.exe"
)

DEFAULT_MODEL_PATH = (
    r"D:\Management_model\models\gemma-3-1b-it-q4_0.gguf"
)

LLAMA_CLI_PATH = os.getenv(
    "LLAMA_CLI_PATH",
    DEFAULT_LLAMA_CLI,
)

GEMMA_MODEL_PATH = os.getenv(
    "GEMMA_MODEL_PATH",
    DEFAULT_MODEL_PATH,
)

GEMMA_CONTEXT = int(
    os.getenv("GEMMA_CONTEXT", "2048")
)

GEMMA_MAX_TOKENS = int(
    os.getenv("GEMMA_MAX_TOKENS", "256")
)

GEMMA_TIMEOUT = int(
    os.getenv("GEMMA_TIMEOUT", "120")
)




_WORD_NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _parse_number_token(value: str) -> Optional[int]:
    """
    Convert either a numeric string or a simple English number
    into an integer.
    """
    value = value.strip().lower()

    if value.isdigit():
        return int(value)

    return _WORD_NUMBERS.get(value)




def extract_duration_minutes(message: str) -> Optional[int]:
    """
    Extract duration from natural language.

    Examples:
        "two hours"      -> 120
        "one hour"       -> 60
        "45 minutes"     -> 45
        "30 seconds"     -> 1
        "2 days"         -> 2880
        "one week"       -> 10080
    """
    if not message:
        return None

    text = message.lower()

    pattern = re.compile(
        r"\b("
        r"\d+(?:\.\d+)?|"
        r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
        r"seventeen|eighteen|nineteen|twenty|thirty|forty|"
        r"fifty|sixty|seventy|eighty|ninety"
        r")\s*"
        r"(seconds?|minutes?|hours?|days?|weeks?)\b",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if not match:
        return None

    number = _parse_number_token(match.group(1))

    if number is None:
        try:
            number = float(match.group(1))
        except (TypeError, ValueError):
            return None

    unit = match.group(2).lower()

    if unit.startswith("second"):
        minutes = number / 60
    elif unit.startswith("minute"):
        minutes = number
    elif unit.startswith("hour"):
        minutes = number * 60
    elif unit.startswith("day"):
        minutes = number * 24 * 60
    elif unit.startswith("week"):
        minutes = number * 7 * 24 * 60
    else:
        return None

    return max(1, int(round(minutes)))


def duration_from_message(message: str) -> Optional[int]:
    """
    Backward-compatible wrapper used by tests and other modules.
    """
    return extract_duration_minutes(message)



def extract_importance(message: str) -> Optional[str]:
    """
    Extract semantic importance level from the user's message.

    Returns:
        critical
        high
        medium
        low
        None
    """
    if not message:
        return None

    text = message.lower()

    # IMPORTANT:
    # Check critical before high.
    if re.search(
        r"\b("
        r"critical|"
        r"extremely important|"
        r"very urgent|"
        r"must do immediately|"
        r"absolute priority"
        r")\b",
        text,
    ):
        return "critical"

    if re.search(
        r"\b("
        r"high priority|"
        r"high-priority|"
        r"urgent|"
        r"very important"
        r")\b",
        text,
    ):
        return "high"

    if re.search(
        r"\b("
        r"important|"
        r"medium priority|"
        r"normal priority"
        r")\b",
        text,
    ):
        return "medium"

    if re.search(
        r"\b("
        r"low priority|"
        r"low-priority|"
        r"not important|"
        r"minor"
        r")\b",
        text,
    ):
        return "low"

    return None


def importance_from_message(message: str) -> int:
    """
    Convert natural-language priority to the integer scale
    used by the database.

    Scale:
        1 = low
        2 = below normal
        3 = normal
        4 = important/high
        5 = critical
    """
    importance = extract_importance(message)

    if importance == "critical":
        return 5

    if importance == "high":
        return 4

    if importance == "medium":
        return 4

    if importance == "low":
        return 1

    return 3


def _normalize_importance_value(
    value: Any,
    original_message: str = "",
) -> int:
    """
    Convert any AI/user importance representation into the integer
    expected by the ManagementData Pydantic schema.

    Deterministic extraction from the original user message has
    priority over Gemma's classification.

    Examples:

        "important" -> 4
        "high"      -> 4
        "critical"  -> 5
        "medium"    -> 3
        "low"       -> 1
        4           -> 4
    """

    
    extracted = extract_importance(original_message)

    if extracted == "critical":
        return 5

    if extracted == "high":
        return 4

    if extracted == "medium":
        return 4

    if extracted == "low":
        return 1

   
    if isinstance(value, bool):
        return 3

    if isinstance(value, int):
        return max(1, min(5, value))

    if isinstance(value, float):
        return max(1, min(5, int(value)))

    if isinstance(value, str):
        normalized = value.strip().lower()

        mapping = {
            "very low": 1,
            "low": 1,
            "minor": 1,

            "below normal": 2,

            "normal": 3,
            "medium": 3,

            "important": 4,
            "high": 4,
            "high priority": 4,

            "critical": 5,
            "urgent": 5,
            "very high": 5,
        }

        if normalized in mapping:
            return mapping[normalized]

        try:
            numeric = int(float(normalized))
            return max(1, min(5, numeric))
        except (TypeError, ValueError):
            pass

    # Safe default
    return 3




_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _next_weekday(
    target_weekday: int,
    today: Optional[date] = None,
) -> date:
    """
    Return the next occurrence of a weekday.
    """
    if today is None:
        today = date.today()

    days_ahead = (target_weekday - today.weekday()) % 7

    if days_ahead == 0:
        days_ahead = 7

    return today + timedelta(days=days_ahead)


def extract_deadline(message: str) -> Optional[date]:
    """
    Extract a calendar deadline from natural language.

    Examples:
        tomorrow
        day after tomorrow
        next Friday
        Friday
        25/09/2026
        25-09-2026
    """
    if not message:
        return None

    text = message.lower()
    today = date.today()

    
    # Day after tomorrow
   
    if re.search(
        r"\bday\s+after\s+tomorrow\b",
        text,
    ):
        return today + timedelta(days=2)

   
    # Tomorrow
    
    if re.search(
        r"\btomorrow\b",
        text,
    ):
        return today + timedelta(days=1)

   
    if re.search(
        r"\btoday\b",
        text,
    ):
        return today

   
    match = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
        text,
    )

    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        try:
            return date(year, month, day)
        except ValueError:
            return None

    if re.search(r"\bnext\s+week\b", text):
        return today + timedelta(days=7)

    
    for weekday_name, weekday_number in _WEEKDAYS.items():
        if re.search(
            rf"\b(?:next\s+)?{weekday_name}\b",
            text,
        ):
            return _next_weekday(
                weekday_number,
                today,
            )

    return None


def deadline_from_message(message: str) -> Optional[str]:
    """
    Backward-compatible deadline wrapper used by tests.

    Examples:

        tomorrow
        tomorrow morning — 09:00 AM
        tomorrow afternoon — 01:00 PM
        tomorrow evening — 06:00 PM
        tomorrow night — 09:00 PM
        day after tomorrow
        2026-09-25
    """
    if not message:
        return None

    text = message.lower()

    if re.search(
        r"\bday\s+after\s+tomorrow\b",
        text,
    ):
        return "day after tomorrow"

    if re.search(
        r"\btomorrow\s+morning\b",
        text,
    ):
        return "tomorrow morning — 09:00 AM"

    if re.search(
        r"\btomorrow\s+afternoon\b",
        text,
    ):
        return "tomorrow afternoon — 01:00 PM"

    if re.search(
        r"\btomorrow\s+evening\b",
        text,
    ):
        return "tomorrow evening — 06:00 PM"

    if re.search(
        r"\btomorrow\s+night\b",
        text,
    ):
        return "tomorrow night — 09:00 PM"

    if re.search(
        r"\btomorrow\b",
        text,
    ):
        return "tomorrow"

    if re.search(
        r"\btoday\b",
        text,
    ):
        return "today"

    deadline = extract_deadline(message)

    if deadline is None:
        return None

    return deadline.isoformat()




def _deadline_phrase_pattern() -> str:
    """
    Regex fragment used to identify the end of a task title.
    Longer phrases must come first.
    """
    weekdays = "|".join(_WEEKDAYS.keys())

    return (
        r"(?:"
        r"day\s+after\s+tomorrow|"
        r"tomorrow|"
        r"today|"
        rf"next\s+(?:{weekdays})|"
        rf"(?:{weekdays})"
        r")"
    )


def extract_task_fallback(
    message: str,
) -> Optional[dict[str, Any]]:
    """
    Deterministically create a task when Gemma fails to produce
    a useful task object.

    Supports examples such as:

        I need an E2E AI Python assignment tomorrow.
        I need to finish my Python assignment tomorrow.
        I have to complete the report by Friday.
        Finish the ML project by Friday.
    """
    if not message:
        return None

    text = message.strip()

    deadline_fragment = _deadline_phrase_pattern()

   
    pattern = re.compile(
        rf"\bI\s+need\s+"
        rf"(?:a|an|the)\s+"
        rf"(.+?)"
        rf"\s+(?:{deadline_fragment})"
        rf"(?:\s*[.!?]|$)",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if match:
        title = match.group(1).strip()

        deadline = extract_deadline(text)

        task: dict[str, Any] = {
            "title": title,
            "description": text,
        }

        if deadline:
            task["deadline"] = deadline.isoformat()

        duration = extract_duration_minutes(text)

        if duration is not None:
            task["estimated_duration"] = duration

        task["importance"] = _normalize_importance_value(
            None,
            text,
        )

        return task

  
    pattern = re.compile(
        rf"\b(?:I\s+need\s+to|"
        rf"I\s+have\s+to|"
        rf"I\s+must)\s+"
        rf"(.+?)"
        rf"\s+(?:{deadline_fragment})"
        rf"(?:\s*[.!?]|$)",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if match:
        title = match.group(1).strip()

        deadline = extract_deadline(text)

        task = {
            "title": title,
            "description": text,
        }

        if deadline:
            task["deadline"] = deadline.isoformat()

        duration = extract_duration_minutes(text)

        if duration is not None:
            task["estimated_duration"] = duration

        task["importance"] = _normalize_importance_value(
            None,
            text,
        )

        return task

   
    pattern = re.compile(
        rf"\b("
        rf"finish|complete|do|submit|prepare|review|work\s+on|"
        rf"study|learn|create|build|write"
        rf")\s+"
        rf"(.+?)"
        rf"\s+(?:{deadline_fragment})"
        rf"(?:\s*[.!?]|$)",
        re.IGNORECASE,
    )

    match = pattern.search(text)

    if match:
        action = match.group(1).strip()
        subject = match.group(2).strip()

        title = f"{action} {subject}".strip()

        deadline = extract_deadline(text)

        task = {
            "title": title,
            "description": text,
        }

        if deadline:
            task["deadline"] = deadline.isoformat()

        duration = extract_duration_minutes(text)

        if duration is not None:
            task["estimated_duration"] = duration

        task["importance"] = _normalize_importance_value(
            None,
            text,
        )

        return task

    return None




def _normalize_task_fields(
    task: dict[str, Any],
    original_message: str,
) -> dict[str, Any]:
    """
    Normalize a single task.

    The original user message is the source of truth for
    deterministic fields such as duration, importance, and
    deadline.
    """
    normalized = dict(task)

   
    title = normalized.get("title")

    if title:
        title = str(title).strip()

        # Fix common spacing corruption from Gemma.
        title = re.sub(
            r"(?i)\b(the|a|an)(?=[a-z])",
            r"\1 ",
            title,
        )

       # Fix split word corruption.
        title = re.sub(
            r"(?i)\ba\s+nd\b",
            "and",
            title,
        )


        # Fix common split-token corruption from Gemma.
        title = re.sub(
            r"\bA\s+I\b",
            "AI",
            title,
        )

        title = re.sub(
            r"(?i)\ba\s+([a-z]{3,})\b",
            r"a\1",
            title,
        )

        # Remove dangling deadline connector.
        title = re.sub(
            r"(?i)\s+\bby\s*$",
            "",
            title,
        )

        # Clean repeated whitespace.
        title = re.sub(
            r"\s+",
            " ",
            title,
        )

        normalized["title"] = title.strip()

   
    description = normalized.get("description")

    if not description:
        normalized["description"] = original_message.strip()

    
    message_duration = extract_duration_minutes(
        original_message
    )

    if message_duration is not None:
        normalized["estimated_duration"] = message_duration
    else:
        raw_duration = normalized.get(
            "estimated_duration"
        )

        if raw_duration is not None:
            try:
                normalized["estimated_duration"] = int(
                    raw_duration
                )
            except (TypeError, ValueError):
                normalized.pop(
                    "estimated_duration",
                    None,
                )

   
    #
    # THIS IS THE IMPORTANT FIX.
    #
    # Gemma can return:
    #
    #     "importance": "medium"
    #
    # but ManagementData requires:
    #
    #     importance: int
    #
    # We convert it BEFORE Pydantic validation.
    #
    normalized["importance"] = _normalize_importance_value(
        normalized.get("importance"),
        original_message,
    )

   
    message_deadline = extract_deadline(
        original_message
    )

    if message_deadline is not None:
        normalized["deadline"] = (
            message_deadline.isoformat()
        )
    else:
        raw_deadline = normalized.get("deadline")

        if isinstance(raw_deadline, date):
            normalized["deadline"] = raw_deadline.isoformat()

        elif raw_deadline is not None:
            normalized["deadline"] = str(
                raw_deadline
            )

    return normalized




def postprocess_management_data(
    data: dict[str, Any],
    original_message: str,
) -> dict[str, Any]:
    """
    Normalize Gemma's output into the structure expected by
    ManagementData.

    This function runs BEFORE Pydantic validation.
    """
    if not isinstance(data, dict):
        data = {}

    result = dict(data)

    
    for key in (
        "tasks",
        "meetings",
        "availability",
        "reminders",
        "rules",
    ):
        value = result.get(key)

        if not isinstance(value, list):
            result[key] = []

   
    normalized_tasks: list[dict[str, Any]] = []

    for task in result["tasks"]:
        if not isinstance(task, dict):
            continue

        normalized_task = _normalize_task_fields(
            task,
            original_message,
        )

        normalized_tasks.append(
            normalized_task
        )

    result["tasks"] = normalized_tasks

    
    
    if not result["tasks"]:
        fallback_task = extract_task_fallback(
            original_message
        )

        if fallback_task:
            result["tasks"] = [
                _normalize_task_fields(
                    fallback_task,
                    original_message,
                )
            ]

    return result




def _extract_balanced_json(
    text: str,
) -> Optional[str]:
    """
    Extract the first balanced JSON object from arbitrary
    llama.cpp output.
    """
    if not text:
        return None

    start_index = text.find("{")

    if start_index == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start_index,
        len(text),
    ):
        char = text[index]

        if escaped:
            escaped = False
            continue

        if char == "\\" and in_string:
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[
                    start_index:index + 1
                ]

    return None


def _extract_json_from_text(
    text: str,
) -> Optional[dict[str, Any]]:
    """
    Parse JSON from raw Gemma/llama.cpp output.

    Handles:
        plain JSON
        ```json ... ```
        surrounding llama.cpp logs
    """
    if not text:
        return None

    text = text.strip()

    
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    
    fenced = re.search(
        r"```(?:json)?\s*(.*?)```",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if fenced:
        candidate = fenced.group(1).strip()

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    
    candidate = _extract_balanced_json(text)

    if candidate:
        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None




def _build_prompt(message: str) -> str:
    """
    Build the extraction prompt for Gemma.
    """
    return f"""
You are the AI secretary for a personal management system.

Your job is to extract actionable management information
from the user's message.

USER MESSAGE:

{message}

Return ONLY valid JSON.

Do not use:
- Markdown
- ```json fences
- Explanations
- Comments
- Extra text
- llama.cpp instructions

Use exactly this structure:

{{
  "tasks": [],
  "meetings": [],
  "availability": [],
  "reminders": [],
  "rules": []
}}

For tasks use:

{{
  "title": "task title",
  "description": "task description",
  "deadline": "YYYY-MM-DD",
  "estimated_duration": 60,
  "importance": 4
}}

Importance scale:
1 = low
2 = below normal
3 = normal
4 = important/high
5 = critical

Important:
If the user says "important", use importance 4.
If the user says "high priority", use importance 4.
If the user says "critical", use importance 5.

Return only JSON.
""".strip()




def _run_gemma(
    prompt: str,
) -> str:
    """
    Run llama.cpp and return its stdout.
    """
    command = [
        LLAMA_CLI_PATH,
        "-m",
        GEMMA_MODEL_PATH,
        "-c",
        str(GEMMA_CONTEXT),
        "-n",
        str(GEMMA_MAX_TOKENS),
        "-p",
        "--no-conversation",
        prompt,
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=GEMMA_TIMEOUT,
        encoding="utf-8",
        errors="replace",
    )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""

    # llama.cpp may place useful output in either stream.
    if stdout.strip():
        return stdout

    return stderr




def extract_information(
    message: str,
) -> dict[str, Any]:
    """
    Main parser entry point.

    1. Ask Gemma for structured data.
    2. Parse JSON.
    3. Normalize deterministic fields.
    4. Fall back to deterministic task extraction when needed.
    """
    if not message or not message.strip():
        return {
            "tasks": [],
            "meetings": [],
            "availability": [],
            "reminders": [],
            "rules": [],
        }

    raw_response = ""

    try:
        prompt = _build_prompt(
            message.strip()
        )

        raw_response = _run_gemma(prompt)

        parsed = _extract_json_from_text(
            raw_response
        )

    except (
        subprocess.SubprocessError,
        OSError,
        TimeoutError,
    ):
        parsed = None

    if not isinstance(parsed, dict):
        parsed = {
            "tasks": [],
            "meetings": [],
            "availability": [],
            "reminders": [],
            "rules": [],
        }

    
    normalized = postprocess_management_data(
        parsed,
        message,
    )

    return normalized




parse_message = extract_information