import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import dateparser


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

NLP_MAX_TOKENS = int(
    os.getenv("NLP_MAX_TOKENS", "180")
)

NLP_TIMEOUT = int(
    os.getenv("NLP_TIMEOUT", "120")
)


SUPPORTED_INTENTS = {
    "schedule_query",
    "task_query",
    "deadline_query",
    "meeting_query",
    "event_query",
    "responsibility_query",
    "budget_query",
    "review_query",
    "general_secretary_query",
    "store_information",
    "unknown",
}


def _empty_result() -> Dict[str, Any]:
    return {
        "intent": "unknown",
        "date_text": None,
        "date": None,
        "time_text": None,
        "time": None,
        "entities": [],
        "query_terms": [],
        "confidence": 0.0,
    }


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
        return max(0.0, min(1.0, number))
    except (TypeError, ValueError):
        return default


def _extract_json_object(
    text: str,
) -> Optional[Dict[str, Any]]:
    """
    Extract the first balanced JSON object from Gemma output.

    Handles:
    - plain JSON
    - ```json ... ```
    - prompt/output noise around JSON
    """

    if not text:
        return None

    text = text.strip()

    try:
        value = json.loads(text)

        if isinstance(value, dict):
            return value

    except json.JSONDecodeError:
        pass

    start = text.find("{")

    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False

            elif char == "\\":
                escaped = True

            elif char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                candidate = text[start:index + 1]

                try:
                    value = json.loads(candidate)

                    if isinstance(value, dict):
                        return value

                except json.JSONDecodeError:
                    return None

    return None


def _run_gemma(prompt: str) -> str:
    if not os.path.exists(LLAMA_CLI_PATH):
        raise RuntimeError(
            f"llama-cli not found: {LLAMA_CLI_PATH}"
        )

    if not os.path.exists(GEMMA_MODEL_PATH):
        raise RuntimeError(
            f"Gemma model not found: {GEMMA_MODEL_PATH}"
        )

    result = subprocess.run(
        [
            LLAMA_CLI_PATH,
            "-m",
            GEMMA_MODEL_PATH,
            "-p",
            prompt,
            "-n",
            str(NLP_MAX_TOKENS),
            "-c",
            str(GEMMA_CONTEXT),
            "-st",
        ],
        capture_output=True,
        text=True,
        timeout=NLP_TIMEOUT,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "Gemma NLP process failed."
        )

    output = (result.stdout or "").strip()

    if not output:
        raise RuntimeError(
            "Gemma returned empty output."
        )

    return output


def _build_question_prompt(
    question: str,
) -> str:
    return f"""
You are the natural-language understanding layer of a personal secretary.

Understand the user's question and return ONLY valid JSON.

User question:

{question}

Return exactly this structure:

{{
  "intent": "schedule_query",
  "date_text": "tomorrow",
  "time_text": null,
  "entities": [],
  "query_terms": [],
  "confidence": 0.95
}}

Allowed intent values:

- schedule_query
- task_query
- deadline_query
- meeting_query
- event_query
- responsibility_query
- budget_query
- review_query
- general_secretary_query
- unknown

IMPORTANT INTENT RULES:

1. Use "schedule_query" ONLY when the user asks about their overall schedule,
   activities, or everything they have planned.

   Examples:

   "What am I doing tomorrow?"

   "What do I have tomorrow?"

   "What's on my schedule tomorrow?"

   "Do I have anything planned tomorrow?"

2. Use "meeting_query" when the question specifically asks about meetings.

   Examples:

   "Do I have any meetings tomorrow?"

   "What meetings do I have tomorrow?"

   "When is my meeting?"

   "Do I have a meeting on Friday?"

3. Use "task_query" when the question specifically asks about tasks or work.

   Examples:

   "What tasks do I have tomorrow?"

   "What work should I do tomorrow?"

   "What do I need to finish?"

4. Use "event_query" when the question specifically asks about events.

   Examples:

   "What events do I have tomorrow?"

   "Do I have any events tomorrow?"

5. Use "deadline_query" when the question asks when something is due
   or asks about a deadline.

   Examples:

   "When is the ABC project due?"

   "What's the deadline for ABC?"

   "When do I need to finish ABC?"

6. Use "responsibility_query" when asking who is responsible for,
   assigned to, or handling something.

   Examples:

   "Who is responsible for ABC?"

   "Who is handling the ABC project?"

   "What work did I give Arun?"

7. Use "budget_query" for money, budget, cost, or amount questions.

   Examples:

   "How much money is allocated to ABC?"

   "What's the budget for the project?"

8. Use "review_query" for review or follow-up questions.

   Examples:

   "When should I review ABC?"

   "When do I need to follow up on ABC?"

9. Use "general_secretary_query" when the question is about stored
   secretary information but does not clearly belong to another category.

10. Use "unknown" only when the question cannot reasonably be classified.

DATE RULES:

11. Extract natural date phrases into "date_text".

Examples:

- today
- tomorrow
- yesterday
- day after tomorrow
- next Monday
- this Friday
- in 2 days
- next week

12. Convert the date to an ISO date in "date" when possible.

13. If the question has no date, "date_text" and "date" may be null.

TIME RULES:

14. Extract explicit time phrases into "time_text".

Examples:

- 5 PM
- 3:30 PM
- tomorrow morning
- at 5 PM

15. If no time is present, use null.

ENTITY RULES:

16. Extract important named entities into "entities".

For example:

Question:

"When is the ABC project due?"

Return:

"entities": ["ABC project"]

Question:

"Who is responsible for Arun's mobile app project?"

Return:

"entities": ["Arun", "mobile app project"]

17. Preserve entity names from the user's question.

Do not invent entities.

QUERY TERMS:

18. Put important searchable concepts into "query_terms".

For example:

Question:

"When is the ABC project due?"

Possible result:

"query_terms": ["ABC project", "deadline"]

19. Do not invent information.

20. confidence must be between 0 and 1.

IMPORTANT:

Do not use "schedule_query" simply because a date such as
"tomorrow" appears.

The requested subject determines the intent.

Return JSON only.

""".strip()


def _normalise_intent(
    value: Any,
) -> str:
    intent = (
        _clean_text(value)
        or "unknown"
    ).lower()

    if intent not in SUPPORTED_INTENTS:
        return "unknown"

    return intent


def _parse_natural_date(
    date_text: Optional[str],
    base_datetime: Optional[datetime] = None,
) -> Optional[str]:
    if not date_text:
        return None

    base = (
        base_datetime
        or datetime.now()
    )

    parsed = dateparser.parse(
        date_text,
        settings={
            "RELATIVE_BASE": base,
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )

    if parsed is None:
        return None

    return parsed.date().isoformat()


def _extract_date_fallback(
    text: str,
    base_datetime: Optional[datetime] = None,
) -> Optional[str]:
    lower = text.lower()

    base = (
        base_datetime
        or datetime.now()
    )

    # More specific expressions must be checked first.
    if re.search(
        r"\bday\s+after\s+tomorrow\b",
        lower,
    ):
        return (
            base + timedelta(days=2)
        ).date().isoformat()

    if re.search(
        r"\byesterday\b",
        lower,
    ):
        return (
            base - timedelta(days=1)
        ).date().isoformat()

    if re.search(
        r"\btomorrow\b",
        lower,
    ):
        return (
            base + timedelta(days=1)
        ).date().isoformat()

    if re.search(
        r"\btoday\b",
        lower,
    ):
        return base.date().isoformat()

    match = re.search(
        r"\bin\s+(\d+)\s+(day|days|week|weeks)\b",
        lower,
    )

    if match:
        amount = int(
            match.group(1)
        )

        unit = match.group(2)

        if "week" in unit:
            amount *= 7

        return (
            base + timedelta(days=amount)
        ).date().isoformat()

    weekday_match = re.search(
    r"\b("
    r"monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday"
    r")\b",
    lower,
    re.IGNORECASE,
    )

    if weekday_match:
        weekday_text = weekday_match.group(1)

        parsed_weekday = dateparser.parse(
            weekday_text,
            settings={
                "RELATIVE_BASE": base,
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )

        if parsed_weekday is not None:
            return parsed_weekday.date().isoformat()

    parsed = dateparser.parse(
        text,
        settings={
            "RELATIVE_BASE": base,
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )

    if parsed is None:
        return None

    return parsed.date().isoformat()


def _extract_time_fallback(
    text: str,
) -> Optional[str]:
    match = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        text.lower(),
    )

    if not match:
        return None

    hour = int(
        match.group(1)
    )

    minute = int(
        match.group(2) or 0
    )

    meridiem = match.group(3)

    if meridiem == "pm" and hour != 12:
        hour += 12

    if meridiem == "am" and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}"


def _normalise_result(
    raw: Dict[str, Any],
    original_text: str,
    base_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:

    result = _empty_result()

    result["intent"] = _normalise_intent(
        raw.get("intent")
    )

    result["date_text"] = _clean_text(
        raw.get("date_text")
    )

    result["time_text"] = _clean_text(
        raw.get("time_text")
    )

    entities = raw.get(
        "entities",
        [],
    )

    if isinstance(
        entities,
        list,
    ):
        result["entities"] = [
            str(item).strip()
            for item in entities
            if str(item).strip()
        ][:10]

    query_terms = raw.get(
        "query_terms",
        [],
    )

    if isinstance(
        query_terms,
        list,
    ):
        result["query_terms"] = [
            str(item).strip()
            for item in query_terms
            if str(item).strip()
        ][:20]

    result["confidence"] = _safe_float(
        raw.get("confidence"),
        0.0,
    )

    result["date"] = _parse_natural_date(
        result["date_text"],
        base_datetime,
    )

    result["time"] = _extract_time_fallback(
        result["time_text"] or ""
    )

    if result["date"] is None:
        result["date"] = _extract_date_fallback(
            original_text,
            base_datetime,
        )

    if result["time"] is None:
        result["time"] = _extract_time_fallback(
            original_text
        )

    return result


def _deterministic_question_understanding(
    question: str,
    base_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:

    result = _empty_result()

    text = question.strip().lower()

    if not text:
        return result

    # Date detection first.
    result["date"] = _extract_date_fallback(
        text,
        base_datetime,
    )

    # More specific date expressions must come first.
    if "day after tomorrow" in text:
        result["date_text"] = (
            "day after tomorrow"
        )

    elif "yesterday" in text:
        result["date_text"] = "yesterday"

    elif "tomorrow" in text:
        result["date_text"] = "tomorrow"

    elif "today" in text:
        result["date_text"] = "today"

    else:
        weekday_match = re.search(
            r"\b("
            r"monday|tuesday|wednesday|thursday|"
            r"friday|saturday|sunday"
            r")\b",
            text,
            re.IGNORECASE,
        )

        if weekday_match:
            result["date_text"] = (
                weekday_match.group(1).lower()
            )

    result["time"] = _extract_time_fallback(
        text
    )

    # Schedule questions.
    if any(
        phrase in text
        for phrase in (
            "what am i doing",
            "what do i have",
            "anything tomorrow",
            "anything today",
            "on my schedule",
            "my schedule",
            "what's happening",
            "whats happening",
            "what did i have",
            "what did i do",
        )
    ):
        result["intent"] = "schedule_query"

    elif (
        "meeting" in text
        or "meetings" in text
    ):
        result["intent"] = "meeting_query"

    elif (
        "event" in text
        or "events" in text
    ):
        result["intent"] = "event_query"

    elif any(
        word in text
        for word in (
            "task",
            "tasks",
            "work on",
            "work do i",
        )
    ):
        result["intent"] = "task_query"

    elif any(
        word in text
        for word in (
            "due",
            "deadline",
        )
    ):
        result["intent"] = "deadline_query"

    elif any(
        word in text
        for word in (
            "responsible",
            "assigned",
            "handling",
        )
    ):
        result["intent"] = (
            "responsibility_query"
        )

    elif any(
        word in text
        for word in (
            "budget",
            "money",
            "cost",
            "amount",
        )
    ):
        result["intent"] = "budget_query"

    elif (
        "review" in text
        or "follow up" in text
    ):
        result["intent"] = "review_query"

    else:
        result["intent"] = (
            "general_secretary_query"
        )

    result["confidence"] = 0.70

    return result


def understand_question(
    question: str,
    base_datetime: Optional[datetime] = None,
    use_gemma: bool = True,
) -> Dict[str, Any]:
    """
    Understand a natural-language secretary question.

    Gemma is preferred for flexible language understanding.
    Deterministic parsing remains the fallback.
    """

    deterministic = (
        _deterministic_question_understanding(
            question,
            base_datetime,
        )
    )

    if not use_gemma:
        return deterministic

    try:
        prompt = _build_question_prompt(
            question
        )

        raw_output = _run_gemma(
            prompt
        )

        parsed = _extract_json_object(
            raw_output
        )

        if not parsed:
            return deterministic

        result = _normalise_result(
            parsed,
            question,
            base_datetime,
        )

        # Deterministic intent classification
        # is authoritative for clear patterns.
        #
        # Gemma is still useful for:
        # - entities
        # - query terms
        # - natural dates
        # - natural times
        # - confidence
        #
        # But Gemma must not override an
        # obvious intent such as meeting_query
        # or deadline_query.

        if (
            deterministic["intent"]
            != "general_secretary_query"
        ):
            result["intent"] = (
                deterministic["intent"]
            )

        if result["date"] is None:
            result["date"] = (
                deterministic["date"]
            )

        if result["date_text"] is None:
            result["date_text"] = (
                deterministic["date_text"]
            )

        if result["time"] is None:
            result["time"] = (
                deterministic["time"]
            )

        if result["time_text"] is None:
            result["time_text"] = (
                deterministic["time_text"]
            )

        if result["intent"] == "unknown":
            return deterministic

        if result["confidence"] < 0.30:
            return deterministic

        return result

    except Exception:
        return deterministic


def understand_message(
    message: str,
    base_datetime: Optional[datetime] = None,
    use_gemma: bool = True,
) -> Dict[str, Any]:
    """
    General entry point.

    For now this focuses on understanding questions.
    Information-storage extraction will be added without
    changing the existing secretary processor.
    """

    text = message.strip()

    if not text:
        return _empty_result()

    if (
        "?" in text
        or re.match(
            r"^(what|when|where|who|whom|whose|which|how|"
            r"did|do|does|can|could|tell|show|have)\b",
            text.lower(),
        )
    ):
        return understand_question(
            text,
            base_datetime=base_datetime,
            use_gemma=use_gemma,
        )

    return {
        "intent": "store_information",
        "date_text": None,
        "date": _extract_date_fallback(
            text,
            base_datetime,
        ),
        "time_text": None,
        "time": _extract_time_fallback(
            text
        ),
        "entities": [],
        "query_terms": [],
        "confidence": 0.60,
    }