
"""
Deterministic source-first extraction for the AI Secretary.

Purpose:
- Extract high-confidence information directly from the user's message.
- Do not depend on Gemma for critical facts.
- Preserve literal names, numbers, assignments, deadlines and reviews.
- Extract explicit task names and task durations from the source text.
- Return the same five-category structure used by secretary_processor.py.
"""

from __future__ import annotations

import re
from typing import Any


def _empty_extraction() -> dict[str, list]:
    return {
        "entities": [],
        "facts": [],
        "relationships": [],
        "events": [],
        "memories": [],
    }


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(value).lower())


def _contains_literal(message: str, value: Any) -> bool:
    target = _normalized(value)
    source = _normalized(message)

    if not target:
        return False

    return target in source


def _add_unique(
    items: list[dict],
    item: dict,
    keys: tuple[str, ...],
) -> None:
    for existing in items:
        if all(
            _normalized(existing.get(key))
            == _normalized(item.get(key))
            for key in keys
        ):
            return

    items.append(item)


def _clean_work_name(value: str) -> str:
    value = _clean(value)

    value = re.sub(
        r"^(?:the|a|an)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"\s+(?:by|before|due|on|at)\s+.+$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value.strip(" ,;:")


# ---------------------------------------------------------------------------
# Assignment extraction
# ---------------------------------------------------------------------------

_NAME_PATTERN = (
    r"[A-Z][A-Za-z.'-]{1,40}"
    r"(?:\s+[A-Z][A-Za-z.'-]{1,40}){0,2}"
)


def _extract_assignments(
    message: str,
    result: dict,
) -> tuple[str | None, str | None]:

    person: str | None = None
    work: str | None = None

    # ---------------------------------------------------------------
    # Pattern 1:
    # "I gave Arun the ABC website project."
    # "I assigned Arun the ABC website project."
    #
    # Important:
    # Stop the person's name before "the/a/an" so that:
    #
    # Arun the ABC website project
    #
    # becomes:
    # person = Arun
    # work   = ABC website project
    # ---------------------------------------------------------------

    pattern = re.compile(
        r"\bI\s+"
        r"(?:gave|assigned)\s+"
        r"(?P<person>[A-Z][A-Za-z.'-]{1,40}(?:\s+[A-Z][A-Za-z.'-]{1,40}){0,2}?)"
        r"\s+"
        r"(?:the|a|an)\s+"
        r"(?P<work>[^.!?\n]+)",
        re.IGNORECASE,
    )

    match = pattern.search(message)

    if match:
        candidate_person = _clean(
            match.group("person")
        )

        candidate_work = _clean_work_name(
            match.group("work")
        )

        if candidate_person and candidate_work:
            person = candidate_person
            work = candidate_work

    # ---------------------------------------------------------------
    # Pattern 2:
    # "I assigned the ABC website project to Arun."
    # "I gave the ABC website project to Arun."
    # ---------------------------------------------------------------

    if not person or not work:

        pattern = re.compile(
            r"\b(?:assigned|gave)\s+"
            r"(?:the|a|an)\s+"
            r"(?P<work>[^.!?\n]+?)\s+"
            r"to\s+"
            r"(?P<person>[A-Z][A-Za-z.'-]{1,40}(?:\s+[A-Z][A-Za-z.'-]{1,40}){0,2})",
            re.IGNORECASE,
        )

        match = pattern.search(message)

        if match:
            candidate_person = _clean(
                match.group("person")
            )

            candidate_work = _clean_work_name(
                match.group("work")
            )

            if candidate_person and candidate_work:
                person = candidate_person
                work = candidate_work

    # ---------------------------------------------------------------
    # Pattern 3:
    # "Arun is responsible for the ABC website project."
    # ---------------------------------------------------------------

    if not person or not work:

        pattern = re.compile(
            r"\b"
            r"(?P<person>[A-Z][A-Za-z.'-]{1,40}(?:\s+[A-Z][A-Za-z.'-]{1,40}){0,2})"
            r"\s+is responsible for\s+"
            r"(?P<work>[^.!?\n]+)",
            re.IGNORECASE,
        )

        match = pattern.search(message)

        if match:
            candidate_person = _clean(
                match.group("person")
            )

            candidate_work = _clean_work_name(
                match.group("work")
            )

            if candidate_person and candidate_work:
                person = candidate_person
                work = candidate_work

    # ---------------------------------------------------------------
    # Validate
    # ---------------------------------------------------------------

    if not person or not work:
        return None, None

    if not _contains_literal(message, person):
        return None, None

    if not _contains_literal(message, work):
        return None, None

    # ---------------------------------------------------------------
    # Determine whether the assigned work is a project or task.
    # ---------------------------------------------------------------

    work_type = (
        "PROJECT"
        if re.search(
            r"\bproject\b",
            work,
            re.IGNORECASE,
        )
        else "TASK"
    )

    # ---------------------------------------------------------------
    # Store PERSON entity.
    # ---------------------------------------------------------------

    _add_unique(
        result["entities"],
        {
            "type": "PERSON",
            "name": person,
            "description": None,
        },
        ("type", "name"),
    )

    # ---------------------------------------------------------------
    # Store PROJECT/TASK entity.
    # ---------------------------------------------------------------

    _add_unique(
        result["entities"],
        {
            "type": work_type,
            "name": work,
            "description": None,
        },
        ("type", "name"),
    )

    # ---------------------------------------------------------------
    # Relationship:
    #
    # Arun --responsible_for--> ABC website project
    # ---------------------------------------------------------------

    _add_unique(
        result["relationships"],
        {
            "source": person,
            "relationship_type": "responsible_for",
            "target": work,
            "confidence": 1.0,
        },
        ("source", "relationship_type", "target"),
    )

    # ---------------------------------------------------------------
    # Assignment event.
    # ---------------------------------------------------------------

    _add_unique(
        result["events"],
        {
            "type": "ASSIGNMENT",
            "title": f"{person} assigned {work}",
            "description": (
                f"{person} was assigned responsibility for {work}."
            ),
            "event_time": None,
            "primary_entity": work,
            "confidence": 1.0,
        },
        ("type", "title", "primary_entity"),
    )

    # ---------------------------------------------------------------
    # Responsibility memory.
    # ---------------------------------------------------------------

    _add_unique(
        result["memories"],
        {
            "memory_type": "responsibility",
            "content": (
                f"{person} is responsible for {work}."
            ),
            "importance": 0.8,
            "confidence": 1.0,
            "entity": work,
        },
        ("memory_type", "content"),
    )

    return person, work

# ---------------------------------------------------------------------------
# Duration extraction
# ---------------------------------------------------------------------------

def _duration_to_minutes(
    value: str,
    unit: str,
) -> int | None:

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    unit = unit.lower()

    if unit.startswith("hour") or unit.startswith("hr"):
        minutes = number * 60
    else:
        minutes = number

    minutes = round(minutes)

    if minutes <= 0:
        return None

    return minutes


def _extract_duration_from_text(text: str) -> int | None:
    """
    Extract one explicit duration from source text.

    Examples:
        120 minutes -> 120
        30 mins -> 30
        2 hours -> 120
        1.5 hours -> 90
        2 hours 30 minutes -> 150
        2 hours and 30 minutes -> 150
    """

    if not text:
        return None

    # ---------------------------------------------------------------
    # Hours + minutes
    # ---------------------------------------------------------------

    match = re.search(
        r"\b"
        r"(?P<hours>\d+(?:\.\d+)?)"
        r"\s*(?:hours?|hrs?)"
        r"\s*(?:and\s*)?"
        r"(?P<minutes>\d+(?:\.\d+)?)"
        r"\s*(?:minutes?|mins?)"
        r"\b",
        text,
        re.IGNORECASE,
    )

    if match:
        hours = float(match.group("hours"))
        minutes = float(match.group("minutes"))

        total = round(hours * 60 + minutes)

        return total if total > 0 else None

    # ---------------------------------------------------------------
    # Hours only
    # ---------------------------------------------------------------

    match = re.search(
        r"\b"
        r"(?P<value>\d+(?:\.\d+)?)"
        r"\s*(?P<unit>hours?|hrs?)"
        r"\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return _duration_to_minutes(
            match.group("value"),
            match.group("unit"),
        )

    # ---------------------------------------------------------------
    # Minutes only
    # ---------------------------------------------------------------

    match = re.search(
        r"\b"
        r"(?P<value>\d+(?:\.\d+)?)"
        r"\s*(?P<unit>minutes?|mins?)"
        r"\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return _duration_to_minutes(
            match.group("value"),
            match.group("unit"),
        )

    return None


def _extract_task_duration(
    message: str,
    task_name: str,
) -> int | None:
    """
    Extract a duration associated with a particular task.

    We first inspect the sentence containing the task name.

    If the task and duration are in nearby sentences, we inspect the
    neighboring sentence.

    As a final safe fallback, we use a duration appearing anywhere
    in the message only when there is exactly one explicit duration.
    """

    if not message or not task_name:
        return None

    sentences = re.split(
        r"(?<=[.!?])\s+",
        message,
    )

    normalized_task = _normalized(task_name)

    # ---------------------------------------------------------------
    # 1. Same sentence
    # ---------------------------------------------------------------

    for sentence in sentences:

        if normalized_task and normalized_task in _normalized(sentence):

            duration = _extract_duration_from_text(sentence)

            if duration is not None:
                return duration

    # ---------------------------------------------------------------
    # 2. Nearby sentence
    # ---------------------------------------------------------------

    for index, sentence in enumerate(sentences):

        if normalized_task and normalized_task in _normalized(sentence):

            nearby = " ".join(
                sentences[
                    max(0, index - 1):
                    min(len(sentences), index + 2)
                ]
            )

            duration = _extract_duration_from_text(nearby)

            if duration is not None:
                return duration

    # ---------------------------------------------------------------
    # 3. Safe fallback: exactly one duration in entire message
    # ---------------------------------------------------------------

    matches = re.findall(
        r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)\b",
        message,
        re.IGNORECASE,
    )

    if len(matches) == 1:
        return _extract_duration_from_text(matches[0])

    return None


# ---------------------------------------------------------------------------
# Direct task extraction
# ---------------------------------------------------------------------------

_DIRECT_TASK_PREFIXES = (
    "prepare",
    "finish",
    "complete",
    "create",
    "make",
    "build",
    "write",
    "review",
    "update",
    "fix",
    "design",
    "develop",
    "check",
    "submit",
    "send",
    "organize",
    "plan",
    "implement",
    "test",
    "deploy",
    "work on",
)


def _looks_like_direct_task(sentence: str) -> bool:
    sentence = _clean(sentence)

    if not sentence:
        return False

    lowered = sentence.lower()

    for prefix in _DIRECT_TASK_PREFIXES:

        if re.match(
            rf"^{re.escape(prefix)}\b",
            lowered,
        ):
            return True

    return False


def _clean_direct_task(sentence: str) -> str:

    task = _clean(sentence)

    # Remove "please".
    task = re.sub(
        r"^(?:please\s+)+",
        "",
        task,
        flags=re.IGNORECASE,
    )

    # ---------------------------------------------------------------
    # Remove duration clauses.
    #
    # Examples:
    #   It will take 120 minutes.
    #   It takes 2 hours.
    #   estimated duration is 120 minutes.
    #   duration is 30 minutes.
    #   time needed is 1 hour.
    # ---------------------------------------------------------------

    task = re.sub(
        r"\s*"
        r"(?:it\s+)?"
        r"(?:will\s+take|takes?|"
        r"estimated\s+(?:duration|time)\s+(?:is|:)|"
        r"duration\s+(?:is|:)|"
        r"time\s+(?:needed|required)\s*(?:is|:))"
        r"\s*"
        r"\d+(?:\.\d+)?\s*"
        r"(?:hours?|hrs?|minutes?|mins?)"
        r"(?:\s*(?:and\s*)?\d+(?:\.\d+)?\s*(?:minutes?|mins?))?"
        r"\b.*$",
        "",
        task,
        flags=re.IGNORECASE,
    )

    # ---------------------------------------------------------------
    # Remove trailing weekday deadline.
    # ---------------------------------------------------------------

    task = re.sub(
        r"\s+(?:by|before|due)\s+"
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
        r"\b.*$",
        "",
        task,
        flags=re.IGNORECASE,
    )

    return task.strip(" .,!?:;-")


def _extract_direct_tasks(
    message: str,
    result: dict,
    project: str | None,
) -> list[str]:

    extracted_tasks: list[str] = []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        message,
    )

    for sentence in sentences:

        sentence = _clean(sentence)

        if not sentence:
            continue

        if not _looks_like_direct_task(sentence):
            continue

        task = _clean_direct_task(sentence)

        if len(task) < 3:
            continue

        if not any(
            task.lower().startswith(prefix.lower())
            for prefix in _DIRECT_TASK_PREFIXES
        ):
            continue

        extracted_tasks.append(task)

        _add_unique(
            result["entities"],
            {
                "type": "TASK",
                "name": task,
                "description": f"Work item: {task}",
            },
            ("type", "name"),
        )

        if project:

            _add_unique(
                result["relationships"],
                {
                    "source": project,
                    "relationship_type": "contains_task",
                    "target": task,
                    "confidence": 1.0,
                },
                ("source", "relationship_type", "target"),
            )

        _add_unique(
            result["memories"],
            {
                "memory_type": "task_context",
                "content": task,
                "importance": 0.7,
                "confidence": 1.0,
                "entity": project or task,
            },
            ("memory_type", "content"),
        )

        duration = _extract_task_duration(
            message,
            task,
        )

        if duration is not None:

            _add_unique(
                result["facts"],
                {
                    "entity": task,
                    "key": "estimated_duration",
                    "value": duration,
                    "value_type": "number",
                    "unit": "minutes",
                    "confidence": 1.0,
                },
                ("entity", "key", "value"),
            )

    return extracted_tasks


# ---------------------------------------------------------------------------
# Existing task extraction
# ---------------------------------------------------------------------------

def _extract_tasks(
    message: str,
    result: dict,
    project: str | None,
) -> None:

    pattern = re.compile(
        r"\b(?:"
        r"needs?\s+to|"
        r"has\s+to|"
        r"have\s+to|"
        r"must|"
        r"should|"
        r"will\s+need\s+to"
        r")\s+"
        r"(?:finish|complete|do|handle|work\s+on)\s+"
        r"(?P<task>.*?)(?=\s+(?:by|before|due)\b|[.!?\n]|$)",
        re.IGNORECASE,
    )

    for match in pattern.finditer(message):

        task = _clean(match.group("task"))

        if not task:
            continue

        task = re.sub(
            r"^(?:the|a|an)\s+",
            "",
            task,
            flags=re.IGNORECASE,
        )

        if len(task) < 2:
            continue

        entity_name = task

        _add_unique(
            result["entities"],
            {
                "type": "TASK",
                "name": entity_name,
                "description": f"Work item: {task}",
            },
            ("type", "name"),
        )

        if project:

            _add_unique(
                result["relationships"],
                {
                    "source": project,
                    "relationship_type": "contains_task",
                    "target": entity_name,
                    "confidence": 1.0,
                },
                ("source", "relationship_type", "target"),
            )

        _add_unique(
            result["memories"],
            {
                "memory_type": "task_context",
                "content": task,
                "importance": 0.7,
                "confidence": 1.0,
                "entity": project or entity_name,
            },
            ("memory_type", "content"),
        )

        duration = _extract_task_duration(
            message,
            task,
        )

        if duration is not None:

            _add_unique(
                result["facts"],
                {
                    "entity": entity_name,
                    "key": "estimated_duration",
                    "value": duration,
                    "value_type": "number",
                    "unit": "minutes",
                    "confidence": 1.0,
                },
                ("entity", "key", "value"),
            )


# ---------------------------------------------------------------------------
# Money / budget extraction
# ---------------------------------------------------------------------------

def _extract_money(
    message: str,
    result: dict,
    project: str | None,
) -> None:

    patterns = [
        re.compile(
            r"(?:₹|INR|Rs\.?|Rupees?)\s*"
            r"(?P<amount>\d{1,3}(?:,\d{3})*|\d+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?P<amount>\d{1,3}(?:,\d{3})*|\d+)\s*"
            r"(?:₹|INR|Rs\.?|Rupees?)\b",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:

        for match in pattern.finditer(message):

            raw_amount = match.group("amount")

            amount = float(
                raw_amount.replace(",", "")
            )

            if amount.is_integer():
                amount = int(amount)

            if not project:
                continue

            key = (
                "budget"
                if re.search(
                    r"\bbudget\b",
                    message,
                    re.IGNORECASE,
                )
                else "amount"
            )

            _add_unique(
                result["facts"],
                {
                    "entity": project,
                    "key": key,
                    "value": amount,
                    "value_type": "number",
                    "unit": "INR",
                    "confidence": 1.0,
                },
                ("entity", "key", "value"),
            )


# ---------------------------------------------------------------------------
# Deadline extraction
# ---------------------------------------------------------------------------

_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _extract_deadlines(
    message: str,
    result: dict,
    project: str | None,
) -> None:

    weekday_pattern = "|".join(_WEEKDAYS)

    patterns = [
        re.compile(
            rf"\bby\s+(?P<day>{weekday_pattern})\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\bdue\s+(?:on\s+)?(?P<day>{weekday_pattern})\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\bdeadline\s+(?:is|on)\s+"
            rf"(?P<day>{weekday_pattern})\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\bbefore\s+(?P<day>{weekday_pattern})\b",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:

        match = pattern.search(message)

        if not match:
            continue

        day = _clean(match.group("day"))

        title = (
            f"{project} deadline: {day}"
            if project
            else f"Deadline: {day}"
        )

        _add_unique(
            result["events"],
            {
                "type": "DEADLINE",
                "title": title,
                "description": f"Deadline is {day}.",
                "event_time": day,
                "primary_entity": project,
                "confidence": 1.0,
            },
            ("type", "title"),
        )


# ---------------------------------------------------------------------------
# Review / follow-up extraction
# ---------------------------------------------------------------------------

def _extract_review(
    message: str,
    result: dict,
    project: str | None,
) -> None:

    pattern = re.compile(
        r"\b(?P<action>"
        r"review|"
        r"follow[\s-]?up|"
        r"check|"
        r"revisit"
        r")\b"
        r"[^.!?\n]{0,100}?"
        r"\b(?P<relative>"
        r"after\s+\d+\s+(?:day|days|week|weeks)|"
        r"in\s+\d+\s+(?:day|days|week|weeks)"
        r")\b",
        re.IGNORECASE,
    )

    match = pattern.search(message)

    if not match:
        return

    action = _clean(
        match.group("action")
    ).lower()

    relative = _clean(
        match.group("relative")
    )

    event_type = (
        "REVIEW"
        if "review" in action
        else "FOLLOW_UP"
    )

    title = (
        f"Review {project} {relative}"
        if project
        else f"{event_type.replace('_', ' ').title()} {relative}"
    )

    _add_unique(
        result["events"],
        {
            "type": event_type,
            "title": title,
            "description": f"{action.title()} requested {relative}.",
            "event_time": relative,
            "primary_entity": project,
            "confidence": 1.0,
        },
        ("type", "title"),
    )

    if project:

        _add_unique(
            result["memories"],
            {
                "memory_type": "follow_up",
                "content": f"{action.title()} {project} {relative}.",
                "importance": 0.7,
                "confidence": 1.0,
                "entity": project,
            },
            ("memory_type", "content"),
        )


# ---------------------------------------------------------------------------
# Public extraction function
# ---------------------------------------------------------------------------

def extract_source_information(
    message: str,
) -> dict[str, list]:

    result = _empty_extraction()

    message = _clean(message)

    if not message:
        return result

    # 1. Explicit assignments.
    _, project = _extract_assignments(
        message,
        result,
    )

    # 2. Existing explicit work instructions.
    _extract_tasks(
        message,
        result,
        project,
    )

    # 3. Direct task statements.
    _extract_direct_tasks(
        message,
        result,
        project,
    )

    # 4. Explicit money.
    _extract_money(
        message,
        result,
        project,
    )

    # 5. Explicit deadline.
    _extract_deadlines(
        message,
        result,
        project,
    )

    # 6. Explicit review/follow-up.
    _extract_review(
        message,
        result,
        project,
    )

    return result


# ---------------------------------------------------------------------------
# Safe merge
# ---------------------------------------------------------------------------

def _model_entity_is_grounded(
    message: str,
    item: dict,
) -> bool:

    name = _clean(item.get("name"))

    if not name:
        return False

    return _contains_literal(
        message,
        name,
    )


def _model_number_is_grounded(
    message: str,
    value: Any,
) -> bool:

    source_numbers = {
        match.replace(",", "")
        for match in re.findall(
            r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?",
            message,
        )
    }

    try:

        numeric = float(value)

        if numeric.is_integer():
            normalized = str(int(numeric))
        else:
            normalized = str(numeric)

        return normalized in source_numbers

    except (TypeError, ValueError):
        return False


def merge_source_first(
    source: dict[str, list],
    model: dict[str, list],
    message: str,
) -> dict[str, list]:

    result = _empty_extraction()

    # ---------------------------------------------------------------
    # Entities
    # ---------------------------------------------------------------

    grounded_entities: dict[str, str] = {}

    for item in source.get("entities", []):

        if not isinstance(item, dict):
            continue

        name = _clean(item.get("name"))

        if not name:
            continue

        _add_unique(
            result["entities"],
            item,
            ("type", "name"),
        )

        grounded_entities[
            _normalized(name)
        ] = name

    for item in model.get("entities", []):

        if not isinstance(item, dict):
            continue

        name = _clean(item.get("name"))

        if not _model_entity_is_grounded(
            message,
            item,
        ):
            continue

        normalized = _normalized(name)

        if normalized in grounded_entities:
            continue

        # Do not allow generic words to become entities.
        if normalized in {
            "client",
            "user",
            "person",
            "someone",
            "they",
            "he",
            "she",
            "it",
            "task",
            "project",
            "report",
            "work",
            "meeting",
        }:
            continue

        _add_unique(
            result["entities"],
            item,
            ("type", "name"),
        )

        grounded_entities[
            normalized
        ] = name

    def resolve_entity(value: Any) -> str | None:

        normalized = _normalized(value)

        if not normalized:
            return None

        return grounded_entities.get(
            normalized
        )

    # ---------------------------------------------------------------
    # Facts
    # ---------------------------------------------------------------

    for item in source.get("facts", []):

        if not isinstance(item, dict):
            continue

        entity = resolve_entity(
            item.get("entity")
        )

        if entity:

            copy = dict(item)
            copy["entity"] = entity

            _add_unique(
                result["facts"],
                copy,
                ("entity", "key", "value"),
            )

    for item in model.get("facts", []):

        if not isinstance(item, dict):
            continue

        entity = resolve_entity(
            item.get("entity")
        )

        if not entity:
            continue

        value_type = str(
            item.get("value_type", "")
        ).lower()

        if value_type == "number":

            if not _model_number_is_grounded(
                message,
                item.get("value"),
            ):
                continue

        copy = dict(item)
        copy["entity"] = entity

        _add_unique(
            result["facts"],
            copy,
            ("entity", "key", "value"),
        )

    # ---------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------

    for collection_name in (
        "source",
        "model",
    ):

        collection = (
            source
            if collection_name == "source"
            else model
        )

        for item in collection.get(
            "relationships",
            [],
        ):

            if not isinstance(item, dict):
                continue

            source_name = resolve_entity(
                item.get("source")
            )

            target_name = resolve_entity(
                item.get("target")
            )

            if not source_name or not target_name:
                continue

            copy = dict(item)
            copy["source"] = source_name
            copy["target"] = target_name

            _add_unique(
                result["relationships"],
                copy,
                (
                    "source",
                    "relationship_type",
                    "target",
                ),
            )

    # ---------------------------------------------------------------
    # Events
    # ---------------------------------------------------------------

    for collection_name in (
        "source",
        "model",
    ):

        collection = (
            source
            if collection_name == "source"
            else model
        )

        for item in collection.get(
            "events",
            [],
        ):

            if not isinstance(item, dict):
                continue

            event_type = _clean(
                item.get("type")
            ).upper()

            # Never allow Gemma to invent a meeting.
            if (
                collection_name == "model"
                and event_type == "MEETING"
                and not re.search(
                    r"\b(meeting|appointment|call)\b",
                    message,
                    re.IGNORECASE,
                )
            ):
                continue

            primary = item.get(
                "primary_entity"
            )

            if primary:

                primary = resolve_entity(
                    primary
                )

                if not primary:
                    continue

            copy = dict(item)

            if primary:
                copy["primary_entity"] = primary

            _add_unique(
                result["events"],
                copy,
                (
                    "type",
                    "title",
                    "primary_entity",
                ),
            )

    # ---------------------------------------------------------------
    # Memories
    # ---------------------------------------------------------------

    for collection_name in (
        "source",
        "model",
    ):

        collection = (
            source
            if collection_name == "source"
            else model
        )

        for item in collection.get(
            "memories",
            [],
        ):

            if not isinstance(item, dict):
                continue

            entity = item.get(
                "entity"
            )

            if entity:

                entity = resolve_entity(
                    entity
                )

                if not entity:
                    continue

            content = _clean(
                item.get("content")
            )

            if not content:
                continue

            copy = dict(item)

            if entity:
                copy["entity"] = entity

            _add_unique(
                result["memories"],
                copy,
                (
                    "memory_type",
                    "content",
                ),
            )

    return result

