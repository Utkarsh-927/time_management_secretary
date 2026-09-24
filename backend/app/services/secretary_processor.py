"""
Secretary memory processor.

Turns a persisted RawNote into durable secretary knowledge:

entities, facts, relationships, events, memories, and operational tasks.

Task creation is source-note based and idempotent, so processing the same

secretary note cannot create duplicate operational tasks.
"""

import ast
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    Entity,
    EntityRelationship,
    Event,
    Fact,
    Memory,
    RawNote,
    Task,
)
from .source_extractor import (
    extract_source_information,
    merge_source_first,
)

DEFAULT_USER_ID = "default"


class SecretaryExtractionError(ValueError):
    """Gemma did not provide usable secretary-schema data."""


LLAMA_CLI_PATH = os.getenv(
    "LLAMA_CLI_PATH",
    r"D:\Management_model\llama.cpp\build\bin\Release\llama-cli.exe",
)

GEMMA_MODEL_PATH = os.getenv(
    "GEMMA_MODEL_PATH",
    r"D:\Management_model\models\gemma-3-1b-it-q4_0.gguf",
)

LLAMA_CONTEXT = int(os.getenv("LLAMA_CONTEXT", "4096"))
LLAMA_MAX_TOKENS = int(os.getenv("SECRETARY_MAX_TOKENS", "220"))
LLAMA_TIMEOUT = int(os.getenv("LLAMA_TIMEOUT", "120"))


def _empty_extraction() -> dict:
    return {
        "entities": [],
        "facts": [],
        "relationships": [],
        "events": [],
        "memories": [],
    }


PASS_TOKEN_LIMITS = {
    "entities": 160,
    "facts": 140,
    "relationships": 120,
    "events": 180,
    "memories": 160,
}


def _secretary_pass_prompt(
    kind: str,
    message: str,
    entity_names: list[str],
) -> str:
    """A deliberately small, single-category prompt for Gemma 3 1B."""

    fields = {
        "entities": "type (PERSON, PROJECT, or TASK), name, description",
        "facts": "entity, key, value, value_type, unit, confidence",
        "relationships": "source, relationship_type, target, confidence",
        "events": "type, title, description, event_time, primary_entity, confidence",
        "memories": "memory_type, content, importance, confidence, entity",
    }[kind]

    rules = {
        "entities": (
            "Extract named people, projects, and meaningful work items only."
        ),
        "facts": (
            "Amounts are facts: preserve numeric value and currency unit."
        ),
        "relationships": (
            "Giving/assigning a project means responsible_for. "
            "Use known names exactly."
        ),
        "events": (
            "Work due Friday is DEADLINE. 'after N days' is REVIEW or "
            "FOLLOW_UP, never a meeting or duration."
        ),
        "memories": (
            "Write only concise durable context supported by the message."
        ),
    }[kind]

    known = (
        f"Known entities: {', '.join(entity_names)}."
        if entity_names
        else "Known entities: none."
    )

    return f"""Extract only {kind} for a personal secretary. Return ONLY one JSON object.
Do not explain or invent. Empty array is allowed.
{rules}
{known}
MESSAGE: {message}
JSON: {{"{kind}":[{{{fields}}}]}}"""


def _run_gemma(prompt: str, max_tokens: int | None = None) -> str:
    if not os.path.isfile(LLAMA_CLI_PATH):
        raise FileNotFoundError(
            f"llama-cli.exe not found: {LLAMA_CLI_PATH}"
        )

    if not os.path.isfile(GEMMA_MODEL_PATH):
        raise FileNotFoundError(
            f"Gemma model not found: {GEMMA_MODEL_PATH}"
        )

    command = [
        LLAMA_CLI_PATH,
        "-m",
        GEMMA_MODEL_PATH,
        "-p",
        prompt,
        "-n",
        str(max_tokens or LLAMA_MAX_TOKENS),
        "-c",
        str(LLAMA_CONTEXT),
        "-st",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=LLAMA_TIMEOUT,
            cwd=os.path.dirname(LLAMA_CLI_PATH),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Gemma secretary extraction timed out."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Gemma secretary extraction failed "
            f"(exit {result.returncode}): {stderr[-2000:]}"
        )

    output = (result.stdout or "").strip()

    if not output:
        raise RuntimeError(
            "Gemma secretary extraction returned an empty response."
        )

    return output


def _extract_secretary_information_gemma(message: str) -> dict:
    """Combine independent, small secretary extraction passes.

    A bad optional pass is isolated; all-empty/all-failed extraction is still
    rejected so a RawNote can never be falsely completed.
    """

    combined = _empty_extraction()
    failures = []
    entity_names: list[str] = []

    for kind in combined:
        try:
            raw = _run_gemma(
                _secretary_pass_prompt(
                    kind,
                    message,
                    entity_names,
                ),
                PASS_TOKEN_LIMITS[kind],
            )

            parsed = parse_secretary_response(raw)
            combined[kind] = parsed[kind]

            if kind == "entities":
                entity_names = [
                    _clean_name(item.get("name"))
                    for item in parsed[kind]
                    if (
                        isinstance(item, dict)
                        and _clean_name(item.get("name"))
                    )
                ]

        except Exception as exc:
            failures.append(f"{kind}: {exc}")

    grounded = _ground_secretary_data(combined, message)
    grounded = _ground_secretary_data(
        _normalize_secretary_semantics(grounded, message),
        message,
    )

    if not any(grounded.values()):
        detail = "; ".join(failures)[-4000:]
        raise SecretaryExtractionError(
            "All secretary extraction passes failed, were empty, "
            "or were ungrounded. " + detail
        )

    return grounded


def extract_secretary_information(message: str) -> dict:
    """
    Source-first secretary extraction.

    Deterministic extraction handles high-confidence information
    directly from the user's message.

    Gemma is then allowed to add additional grounded information.

    If Gemma fails but deterministic extraction succeeded,
    the note can still be processed safely.
    """

    # ---------------------------------------------------------------
    # 1. Deterministic extraction from the original source
    # ---------------------------------------------------------------

    source_data = extract_source_information(message)

    # ---------------------------------------------------------------
    # 2. Optional AI enrichment
    # ---------------------------------------------------------------

    model_data = _empty_extraction()
    model_error = None

    try:
        model_data = _extract_secretary_information_gemma(message)

    except (
        SecretaryExtractionError,
        RuntimeError,
        FileNotFoundError,
        TimeoutError,
        OSError,
    ) as exc:
        # Gemma is enrichment, not the source of truth.
        model_error = exc

    # ---------------------------------------------------------------
    # 3. Safe source-first merge
    # ---------------------------------------------------------------

    combined = merge_source_first(
        source_data,
        model_data,
        message,
    )

    # ---------------------------------------------------------------
    # 4. Final safety check
    # ---------------------------------------------------------------

    if not any(combined.values()):
        detail = ""

        if model_error:
            detail = f" Gemma error: {model_error}"

        raise SecretaryExtractionError(
            "Secretary extraction produced no grounded information."
            + detail
        )

    return combined


def _json_object_from_response(response: Any) -> str:
    """Return the final balanced JSON object, allowing model prose/fences.

    llama-cli echoes the prompt before the generated answer, so the final
    object is the only candidate that can safely represent the model output.
    """

    if isinstance(response, dict):
        return json.dumps(response)

    text = str(response or "").strip()

    text = re.sub(
        r"```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).replace("```", "")

    if "{" not in text:
        raise SecretaryExtractionError(
            "Gemma response did not contain a JSON object."
        )

    final_object = None
    search_from = 0

    while True:
        start = text.find("{", search_from)

        if start < 0:
            break

        depth = 0
        quoted = False
        escaped = False

        for index, char in enumerate(text[start:], start):
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue

            if char == '"':
                quoted = True

            elif char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    final_object = text[start:index + 1]
                    search_from = index + 1
                    break

        else:
            search_from = start + 1

    if final_object is None:
        raise SecretaryExtractionError(
            "Gemma response contained an incomplete JSON object."
        )

    return final_object


def _repair_secretary_json(text: str) -> str:
    """Apply only conservative repairs common in small-model JSON output."""

    # Missing comma between a completed value and the next quoted object key.
    text = re.sub(
        r'([}\]])\s*("(?:entities|facts|relationships|events|memories)"\s*:)',
        r"\1,\2",
        text,
    )

    # Obvious missing comma inside nested objects.
    text = re.sub(
        r'("(?:[^"\\]|\\.)*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?)\s+'
        r'("[A-Za-z_][A-Za-z0-9_]*"\s*:)',
        r"\1,\2",
        text,
    )

    # JSON does not permit a trailing comma before an object/array close.
    return re.sub(r",\s*([}\]])", r"\1", text)


def _response_context(response: Any) -> str:
    """Bounded raw-model diagnostic; no prompt/environment data."""

    text = str(response or "")
    suffix = "…" if len(text) > 4000 else ""

    return (
        f" Raw response (truncated): "
        f"{text[:4000]!r}{suffix}"
    )


def parse_secretary_response(response: Any) -> dict:
    """Extract, repair where safe, and validate secretary-only model output."""

    try:
        candidate = _json_object_from_response(response)
        data = json.loads(candidate)

    except (
        SecretaryExtractionError,
        json.JSONDecodeError,
    ) as initial_error:

        try:
            repaired = (
                _repair_secretary_json(candidate)
                if "candidate" in locals()
                else ""
            )
            data = json.loads(repaired)

        except json.JSONDecodeError:

            try:
                data = ast.literal_eval(repaired)

            except (SyntaxError, ValueError) as exc:
                raise SecretaryExtractionError(
                    f"Gemma returned invalid secretary JSON: "
                    f"{initial_error}."
                    f"{_response_context(response)}"
                ) from exc

    if not isinstance(data, dict):
        raise SecretaryExtractionError(
            "Secretary response must be a JSON object."
            + _response_context(response)
        )

    expected = set(_empty_extraction())

    if not expected.intersection(data):
        raise SecretaryExtractionError(
            "Response does not use the secretary JSON schema."
            + _response_context(response)
        )

    result = _empty_extraction()

    for key in result:
        value = data.get(key, [])

        if value is None:
            value = []

        result[key] = (
            value if isinstance(value, list)
            else [value]
        )

    if not any(result.values()):
        raise SecretaryExtractionError(
            "Secretary extraction was empty; refusing to mark note completed."
            + _response_context(response)
        )

    return result


def _normalized_literal(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        _clean_name(value).lower(),
    )


def _ground_secretary_data(
    data: dict,
    message: str,
) -> dict:
    """Keep only records whose literal names/numbers occur in source text."""

    source = _normalized_literal(message)

    result = _empty_extraction()
    canonical: dict[str, str] = {}

    for item in data.get("entities", []):
        if not isinstance(item, dict):
            continue

        name = _clean_name(item.get("name"))
        normalized = _normalized_literal(name)

        if name and normalized and normalized in source:
            result["entities"].append(item)
            canonical[normalized] = name

    def resolve(name: Any) -> str | None:
        return canonical.get(
            _normalized_literal(name)
        )

    numeric_literals = set(
        re.findall(
            r"(?<![\w.])-?\d+(?:\.\d+)?",
            message,
        )
    )

    for item in data.get("facts", []):
        if not isinstance(item, dict):
            continue

        if not resolve(item.get("entity")):
            continue

        value = item.get("value")

        if str(
            item.get("value_type", "")
        ).lower() == "number":

            normalized_value = (
                str(value).rstrip("0").rstrip(".")
                if isinstance(value, float)
                else str(value)
            )

            if normalized_value not in numeric_literals:
                continue

        item = dict(item)
        item["entity"] = resolve(item["entity"])

        result["facts"].append(item)

    for item in data.get("relationships", []):
        if not isinstance(item, dict):
            continue

        source_name = resolve(item.get("source"))
        target_name = resolve(item.get("target"))

        if source_name and target_name:
            item = dict(
                item,
                source=source_name,
                target=target_name,
            )
            result["relationships"].append(item)

    for item in data.get("events", []):
        if not isinstance(item, dict):
            continue

        primary = item.get("primary_entity")

        if primary and not resolve(primary):
            continue

        event_type = _clean_name(
            item.get("type")
        ).upper()

        if (
            event_type == "MEETING"
            and not re.search(
                r"\b(meeting|appointment|call)\b",
                message,
                re.I,
            )
        ):
            continue

        if (
            event_type == "DEADLINE"
            and "friday" not in message.lower()
        ):
            continue

        if (
            event_type in {"REVIEW", "FOLLOW_UP"}
            and not re.search(
                r"after\s+\d+\s+days?",
                message,
                re.I,
            )
        ):
            continue

        if primary:
            item = dict(
                item,
                primary_entity=resolve(primary),
            )

        result["events"].append(item)

    for item in data.get("memories", []):
        if not isinstance(item, dict):
            continue

        entity = item.get("entity")

        if entity and not resolve(entity):
            continue

        content = _clean_name(item.get("content"))

        named = re.findall(
            r"\b[A-Z][A-Za-z]+\b",
            content,
        )

        if any(
            _normalized_literal(token) not in source
            for token in named
        ):
            continue

        if entity:
            item = dict(
                item,
                entity=resolve(entity),
            )

        result["memories"].append(item)

    return result


def _normalize_secretary_semantics(
    data: dict,
    message: str,
) -> dict:
    """Correct known small-model category mistakes using explicit text only."""

    entities = data["entities"]

    project = next(
        (
            _clean_name(item.get("name"))
            for item in entities
            if (
                isinstance(item, dict)
                and str(item.get("type", "")).upper() == "PROJECT"
            )
        ),
        None,
    )

    people = [
        _clean_name(item.get("name"))
        for item in entities
        if (
            isinstance(item, dict)
            and str(item.get("type", "")).upper() == "PERSON"
            and _clean_name(item.get("name"))
        )
    ]

    normalized_entities = []
    message_lower = message.lower()

    for item in entities:
        if not isinstance(item, dict):
            continue

        item_type = str(
            item.get("type", "")
        ).upper()

        if (
            item_type in {"AMOUNT", "MONEY", "NUMBER"}
            and item.get("value") is not None
            and project
        ):
            data["facts"].append({
                "entity": project,
                "key": (
                    "budget"
                    if "budget" in message_lower
                    else "amount"
                ),
                "value": item["value"],
                "value_type": "number",
                "unit": (
                    item.get("currency")
                    or item.get("unit")
                ),
            })

        elif item_type == "DEADLINE" and project:
            deadline = _clean_name(
                item.get("name")
                or item.get("key")
            )

            data["events"].append({
                "type": "DEADLINE",
                "title": f"{project} due {deadline}",
                "event_time": deadline or None,
                "primary_entity": project,
            })

        elif (
            item_type in {
                "REVIEW",
                "FOLLOW_UP",
                "FOLLOWUP",
            }
            and project
        ):
            match = re.search(
                r"after\s+\d+\s+days?",
                message,
                re.IGNORECASE,
            )

            data["events"].append({
                "type": (
                    "FOLLOW_UP"
                    if item_type != "REVIEW"
                    else "REVIEW"
                ),
                "title": _clean_name(
                    item.get("title")
                    or item.get("name")
                    or "Follow up"
                ),
                "event_time": (
                    match.group(0)
                    if match
                    else None
                ),
                "primary_entity": project,
            })

        else:
            normalized_entities.append(item)

    data["entities"] = normalized_entities

    if (
        project
        and people
        and re.search(
            r"\b(gave|assigned)\b",
            message,
            re.IGNORECASE,
        )
    ):
        data["relationships"].append({
            "source": people[0],
            "relationship_type": "responsible_for",
            "target": project,
        })

    return data


def _clean_name(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )


def _safe_score(
    value: Any,
    default: float = 0.5,
) -> float:
    """
    Safely normalize Gemma confidence/importance values.

    Accepts:
    - numeric values: 0.0 to 1.0
    - numeric strings
    - common qualitative LLM values such as:
      high, medium, low, known, unknown

    Invalid values fall back to the supplied default.
    """

    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return 1.0 if value else 0.0

    if isinstance(value, (int, float)):
        return max(
            0.0,
            min(1.0, float(value)),
        )

    text = str(value).strip().lower()

    try:
        return max(
            0.0,
            min(1.0, float(text)),
        )
    except (TypeError, ValueError):
        pass

    qualitative = {
        "very high": 0.95,
        "high": 0.85,
        "medium": 0.60,
        "moderate": 0.60,
        "low": 0.30,
        "very low": 0.15,
        "certain": 1.0,
        "high confidence": 0.90,
        "medium confidence": 0.60,
        "low confidence": 0.30,
        "known": 1.0,
        "unknown": 0.0,
    }

    return qualitative.get(
        text,
        default,
    )


def _canonical_key(
    entity_type: str,
    name: str,
) -> str:
    return (
        f"{entity_type.strip().upper()}:"
        f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}"
    )


def _get_or_create_entity(
    db: Session,
    user_id: str,
    entity_type: str,
    name: str,
    description: str | None,
) -> Entity:

    entity_type = str(
        entity_type or "OTHER"
    ).upper().strip()

    name = _clean_name(name)

    key = _canonical_key(
        entity_type,
        name,
    )

    entity = (
        db.query(Entity)
        .filter(
            Entity.user_id == user_id,
            Entity.canonical_key == key,
        )
        .first()
    )

    if entity:
        if description and not entity.description:
            entity.description = description
        return entity

    entity = Entity(
        user_id=user_id,
        entity_type=entity_type,
        name=name,
        canonical_key=key,
        description=description,
        status="active",
    )

    db.add(entity)
    db.flush()

    return entity


def _parse_datetime(
    value: Any,
) -> datetime | None:

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
        return parsed.replace(tzinfo=None)

    except ValueError:
        pass

    try:
        return datetime.combine(
            date.fromisoformat(text),
            datetime.min.time(),
        )

    except ValueError:
        return None


def _next_weekday(
    target_name: str,
    base: date,
) -> date:

    names = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    target = names[target_name.lower()]

    delta = (
        target - base.weekday()
    ) % 7

    return base + timedelta(days=delta)


def _repair_relative_event_time(
    value: Any,
    raw_text: str,
    now_date: date,
) -> Any:

    if value is None:
        text = raw_text.lower()

        match = re.search(
            r"after\s+(\d+)\s+days?",
            text,
        )

        if match:
            days = int(match.group(1))

            return datetime.combine(
                now_date + timedelta(days=days),
                datetime.min.time(),
            )

        return None

    text = str(value).strip().lower()

    if text == "friday":
        return datetime.combine(
            _next_weekday(
                "friday",
                now_date,
            ),
            datetime.min.time(),
        )

    match = re.fullmatch(
        r"after\s+(\d+)\s+days?",
        text,
    )

    if match:
        days = int(match.group(1))

        return datetime.combine(
            now_date + timedelta(days=days),
            datetime.min.time(),
        )

    return _parse_datetime(value)


def _set_fact_value(
    fact: Fact,
    value: Any,
    value_type: str,
) -> None:

    fact.value_text = None
    fact.value_number = None
    fact.value_datetime = None
    fact.value_boolean = None
    fact.value_json = None

    value_type = str(
        value_type or "text"
    ).lower()

    fact.value_type = value_type

    if value_type == "number":
        try:
            fact.value_number = float(value)

        except (TypeError, ValueError):
            fact.value_text = str(value)
            fact.value_type = "text"

    elif value_type == "date":
        parsed = _parse_datetime(value)

        if parsed:
            fact.value_datetime = parsed

        else:
            fact.value_text = str(value)
            fact.value_type = "text"

    elif value_type == "boolean":
        fact.value_boolean = bool(value)

    elif value_type == "json":
        fact.value_json = value

    else:
        fact.value_text = (
            str(value)
            if value is not None
            else None
        )

def _extract_task_duration_minutes(
    raw_text: str,
    task_title: str,
) -> int | None:
    """
    Extract an explicit task duration from the original
    user message.

    Examples:

        "Prepare the report. It will take 120 minutes."
        -> 120

        "Prepare the report. It will take 2 hours."
        -> 120

        "Build the website, estimated duration is 3 hours."
        -> 180

    The original source text is the source of truth.
    We never invent a duration.
    """

    if not raw_text:
        return None

    text = raw_text.strip()

    # ---------------------------------------------------------
    # 1. Combined hours + minutes
    #
    # "1 hour 30 minutes"
    # "2 hours and 15 minutes"
    # ---------------------------------------------------------

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:hours?|hrs?)"
        r"\s*(?:and\s*)?"
        r"(\d+(?:\.\d+)?)\s*"
        r"(?:minutes?|mins?)\b",
        text,
        re.IGNORECASE,
    )

    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2))

        return round(
            hours * 60 + minutes
        )

    # ---------------------------------------------------------
    # 2. Decimal hours
    #
    # "1.5 hours"
    # ---------------------------------------------------------

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:hours?|hrs?)\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return round(
            float(match.group(1)) * 60
        )

    # ---------------------------------------------------------
    # 3. Minutes
    #
    # "120 minutes"
    # "30 mins"
    # ---------------------------------------------------------

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:minutes?|mins?)\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return round(
            float(match.group(1))
        )

    return None        


def _create_operational_tasks(
    db: Session,
    note: RawNote,
    user_id: str,
    data: dict,
    entity_map: dict[str, Entity],
) -> int:
    """
    Convert grounded secretary knowledge into operational Task rows.

    Only creates tasks when the source note clearly contains a task/work item.
    The source note is the source of truth.

    Idempotency:
    - same source_note_id + same normalized task title -> no duplicate
    """

    created_count = 0

    # ---------------------------------------------------------------
    # 1. Find project and person relationships
    # ---------------------------------------------------------------

    project_entities: dict[str, Entity] = {}
    person_entities: dict[str, Entity] = {}

    for entity in entity_map.values():
        entity_type = str(
            entity.entity_type or ""
        ).upper()

        if entity_type == "PROJECT":
            project_entities[
                entity.name.lower()
            ] = entity

        elif entity_type == "PERSON":
            person_entities[
                entity.name.lower()
            ] = entity

    # ---------------------------------------------------------------
    # 2. Find responsible person -> project relationships
    # ---------------------------------------------------------------

    responsible_people: dict[int, Entity] = {}

    for item in data.get("relationships", []):
        if not isinstance(item, dict):
            continue

        relationship_type = _clean_name(
            item.get("relationship_type")
        ).lower()

        if relationship_type != "responsible_for":
            continue

        source = entity_map.get(
            _clean_name(
                item.get("source")
            ).lower()
        )

        target = entity_map.get(
            _clean_name(
                item.get("target")
            ).lower()
        )

        if (
            source
            and target
            and str(source.entity_type).upper() == "PERSON"
        ):
            responsible_people[target.id] = source

    # ---------------------------------------------------------------
    # 3. Find project -> task relationships
    # ---------------------------------------------------------------

    task_projects: dict[str, Entity] = {}

    for item in data.get("relationships", []):
        if not isinstance(item, dict):
            continue

        relationship_type = _clean_name(
            item.get("relationship_type")
        ).lower()

        if relationship_type != "contains_task":
            continue

        project = entity_map.get(
            _clean_name(
                item.get("source")
            ).lower()
        )

        task_entity = entity_map.get(
            _clean_name(
                item.get("target")
            ).lower()
        )

        if not project or not task_entity:
            continue

        if str(project.entity_type).upper() != "PROJECT":
            continue

        task_projects[
            task_entity.name.lower()
        ] = project

    # ---------------------------------------------------------------
    # 4. Extract deadlines from events
    # ---------------------------------------------------------------

    project_deadlines: dict[int, datetime] = {}

    for item in data.get("events", []):
        if not isinstance(item, dict):
            continue

        event_type = _clean_name(
            item.get("type")
        ).upper()

        if event_type != "DEADLINE":
            continue

        project_name = _clean_name(
            item.get("primary_entity")
        )

        project = entity_map.get(
            project_name.lower()
        )

        if not project:
            continue

        deadline = _repair_relative_event_time(
            item.get("event_time"),
            note.raw_text,
            note.created_at.date(),
        )

        if deadline:
            project_deadlines[
                project.id
            ] = deadline

    # ---------------------------------------------------------------
    # 5. Identify actual task entities
    # ---------------------------------------------------------------

    task_entities = []

    for item in data.get("entities", []):
        if not isinstance(item, dict):
            continue

        entity_type = str(
            item.get("type", "")
        ).upper()

        if entity_type != "TASK":
            continue

        task_name = _clean_name(
            item.get("name")
        )

        if task_name:
            task_entity = entity_map.get(
                task_name.lower()
            )

            if task_entity:
                task_entities.append(
                    task_entity
                )

    # ---------------------------------------------------------------
    # 6. Create operational tasks
    # ---------------------------------------------------------------

    for task_entity in task_entities:

        task_title = _clean_name(
            task_entity.name
        )

        if not task_title:
            continue

        # -----------------------------------------------------------
        # Improve title using the actual task context.
        #
        # "homepage and contact form"
        # becomes
        # "Finish homepage and contact form"
        # -----------------------------------------------------------

        title_lower = task_title.lower()

        if not title_lower.startswith(
            (
                "finish ",
                "complete ",
                "do ",
                "create ",
                "build ",
                "prepare ",
                "review ",
                "update ",
                "fix ",
                "send ",
                "submit ",
            )
        ):
            task_title = (
                f"Finish {task_title}"
            )

        # -----------------------------------------------------------
        # Duplicate protection
        # -----------------------------------------------------------

        existing = (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.source_note_id == note.id,
                Task.title == task_title,
            )
            .first()
        )

        if existing:
            continue

        # -----------------------------------------------------------
        # Find project
        # -----------------------------------------------------------

        project = task_projects.get(
            task_entity.name.lower()
        )

        # -----------------------------------------------------------
        # Find assignee
        # -----------------------------------------------------------

        assignee = None

        if project:
            assignee = responsible_people.get(
                project.id
            )

        # -----------------------------------------------------------
        # Find deadline
        # -----------------------------------------------------------

        deadline = None

        if project:
            deadline = project_deadlines.get(
                project.id
            )

               # -----------------------------------------------------------
        # Task duration
        #
        # Prefer the task-specific estimated_duration fact extracted
        # from the original source note.
        #
        # Example:
        # "Prepare the quarterly client report. It will take
        # 120 minutes."
        #
        # -> estimated_duration = 120
        # -> remaining_duration = 120
        #
        # If no task-specific fact exists, use the deterministic
        # source-text extractor as a safe fallback.
        # -----------------------------------------------------------
        estimated_duration = None

        for fact_item in data.get("facts", []):
            if not isinstance(fact_item, dict):
                continue

            fact_entity = _clean_name(
                fact_item.get("entity")
            ).lower()

            fact_key = _clean_name(
                fact_item.get("key")
            ).lower()

            if (
                fact_entity == task_entity.name.lower()
                and fact_key == "estimated_duration"
            ):
                value = fact_item.get("value")

                try:
                    if str(
                        fact_item.get("value_type", "")
                    ).lower() == "number":
                        estimated_duration = round(
                            float(value)
                        )
                except (TypeError, ValueError):
                    estimated_duration = None

                break

        # Safe fallback for older/source extraction cases.
        if estimated_duration is None:
            estimated_duration = _extract_task_duration_minutes(
                note.raw_text,
                task_title,
            )

        # Never allow an invalid or non-positive duration.
        if (
            estimated_duration is not None
            and estimated_duration <= 0
        ):
            estimated_duration = None

        task = Task(
            user_id=user_id,
            title=task_title,
            description=(
                task_entity.description
                or f"Task captured from secretary note: "
                   f"{task_title}"
            ),
            deadline=deadline,
            estimated_duration=estimated_duration,
            remaining_duration=estimated_duration,
            progress_percent=0,
            importance=3,
            urgency=3,
            priority_score=0.0,
            status="pending",
            project_entity_id=(
                project.id
                if project
                else None
            ),
            assignee_entity_id=(
                assignee.id
                if assignee
                else None
            ),
            source_note_id=note.id,
            context={
                "source": "secretary",
                "source_note_id": note.id,
            },
            energy_required=None,
        )

        db.add(task)
        db.flush()

        created_count += 1

    return created_count


def process_raw_note(
    db: Session,
    note: RawNote,
    user_id: str = DEFAULT_USER_ID,
    create_operational_tasks=True,
) -> dict:
    """
    Process one RawNote exactly once.

    Returns counts for each knowledge type.
    """

    if (
        note.processed
        and note.processing_status == "completed"
    ):
        return {
            "raw_note_id": note.id,
            "status": "already_processed",
            "entities": 0,
            "facts": 0,
            "relationships": 0,
            "events": 0,
            "memories": 0,
            "tasks": 0,
        }

    note.processing_status = "processing"
    note.processing_error = None

    db.flush()

    try:
        data = extract_secretary_information(
            note.raw_text
        )

        entity_map: dict[str, Entity] = {}

        # -----------------------------------------------------------
        # 1. Entities
        # -----------------------------------------------------------

        for item in data["entities"]:
            if not isinstance(item, dict):
                continue

            name = _clean_name(
                item.get("name")
            )

            if not name:
                continue

            entity = _get_or_create_entity(
                db,
                user_id,
                item.get("type", "OTHER"),
                name,
                item.get("description"),
            )

            entity_map[name.lower()] = entity

        # -----------------------------------------------------------
        # 2. Ensure referenced entities exist
        # -----------------------------------------------------------

        for key in (
            "facts",
            "relationships",
            "events",
            "memories",
        ):
            for item in data[key]:

                if not isinstance(item, dict):
                    continue

                candidates = []

                if key == "facts":
                    candidates = [
                        item.get("entity")
                    ]

                elif key == "relationships":
                    candidates = [
                        item.get("source"),
                        item.get("target"),
                    ]

                elif key == "events":
                    candidates = [
                        item.get("primary_entity")
                    ]

                elif key == "memories":
                    candidates = [
                        item.get("entity")
                    ]

                for raw_name in candidates:
                    name = _clean_name(raw_name)

                    if (
                        name
                        and name.lower() not in entity_map
                    ):
                        entity = _get_or_create_entity(
                            db,
                            user_id,
                            "OTHER",
                            name,
                            None,
                        )

                        entity_map[
                            name.lower()
                        ] = entity

        # -----------------------------------------------------------
        # 3. Facts
        # -----------------------------------------------------------

        fact_count = 0

        for item in data["facts"]:
            if not isinstance(item, dict):
                continue

            entity = entity_map.get(
                _clean_name(
                    item.get("entity")
                ).lower()
            )

            key = _clean_name(
                item.get("key")
            )

            if not entity or not key:
                continue

            if (
                db.query(Fact)
                .filter(
                    Fact.user_id == user_id,
                    Fact.entity_id == entity.id,
                    Fact.key == key,
                    Fact.source_note_id == note.id,
                )
                .first()
            ):
                continue

            current = (
                db.query(Fact)
                .filter(
                    Fact.user_id == user_id,
                    Fact.entity_id == entity.id,
                    Fact.key == key,
                    Fact.is_current.is_(True),
                )
                .all()
            )

            for old in current:
                old.is_current = False
                old.valid_until = datetime.utcnow()

            fact = Fact(
                user_id=user_id,
                entity_id=entity.id,
                key=key,
                unit=item.get("unit"),
                confidence=_safe_score(
                    item.get("confidence"),
                    1.0,
                ),
                source_note_id=note.id,
                is_current=True,
                valid_from=note.created_at,
            )

            _set_fact_value(
                fact,
                item.get("value"),
                item.get(
                    "value_type",
                    "text",
                ),
            )

            db.add(fact)
            fact_count += 1

        # -----------------------------------------------------------
        # 4. Relationships
        # -----------------------------------------------------------

        relationship_count = 0

        for item in data["relationships"]:
            if not isinstance(item, dict):
                continue

            source = entity_map.get(
                _clean_name(
                    item.get("source")
                ).lower()
            )

            target = entity_map.get(
                _clean_name(
                    item.get("target")
                ).lower()
            )

            rel_type = _clean_name(
                item.get("relationship_type")
            )

            if (
                not source
                or not target
                or not rel_type
            ):
                continue

            existing = (
                db.query(EntityRelationship)
                .filter(
                    EntityRelationship.user_id == user_id,
                    EntityRelationship.source_entity_id == source.id,
                    EntityRelationship.target_entity_id == target.id,
                    EntityRelationship.relationship_type == rel_type,
                    EntityRelationship.is_current.is_(True),
                )
                .first()
            )

            if existing:
                existing.source_note_id = note.id
                continue

            db.add(
                EntityRelationship(
                    user_id=user_id,
                    source_entity_id=source.id,
                    target_entity_id=target.id,
                    relationship_type=rel_type,
                    confidence=_safe_score(
                        item.get("confidence"),
                        1.0,
                    ),
                    source_note_id=note.id,
                    is_current=True,
                    valid_from=note.created_at,
                )
            )

            relationship_count += 1

        # -----------------------------------------------------------
        # 5. Events
        # -----------------------------------------------------------

        event_count = 0

        for item in data["events"]:
            if not isinstance(item, dict):
                continue

            title = _clean_name(
                item.get("title")
            )

            if not title:
                continue

            event_time = _repair_relative_event_time(
                item.get("event_time"),
                note.raw_text,
                note.created_at.date(),
            )

            end_time = _parse_datetime(
                item.get("end_time")
            )

            primary = entity_map.get(
                _clean_name(
                    item.get("primary_entity")
                ).lower()
            )

            existing = (
                db.query(Event)
                .filter(
                    Event.user_id == user_id,
                    Event.source_note_id == note.id,
                    Event.event_type
                    == _clean_name(
                        item.get("type")
                        or "OTHER"
                    ).upper(),
                    Event.title == title,
                )
                .first()
            )

            if existing:
                continue

            db.add(
                Event(
                    user_id=user_id,
                    event_type=_clean_name(
                        item.get("type")
                        or "OTHER"
                    ).upper(),
                    title=title,
                    description=item.get("description"),
                    event_time=event_time,
                    end_time=end_time,
                    primary_entity_id=(
                        primary.id
                        if primary
                        else None
                    ),
                    source_note_id=note.id,
                    confidence=_safe_score(
                        item.get("confidence"),
                        1.0,
                    ),
                )
            )

            event_count += 1

        # -----------------------------------------------------------
        # 6. Memories
        # -----------------------------------------------------------

        memory_count = 0

        for item in data["memories"]:
            if not isinstance(item, dict):
                continue

            content = _clean_name(
                item.get("content")
            )

            if not content:
                continue

            existing = (
                db.query(Memory)
                .filter(
                    Memory.user_id == user_id,
                    Memory.source_note_id == note.id,
                    Memory.content == content,
                )
                .first()
            )

            if existing:
                continue

            primary = entity_map.get(
                _clean_name(
                    item.get("entity")
                ).lower()
            )

            db.add(
                Memory(
                    user_id=user_id,
                    memory_type=_clean_name(
                        item.get("memory_type")
                        or item.get("type")
                        or "general"
                    ),
                    content=content,
                    importance=_safe_score(
                        item.get("importance"),
                        0.5,
                    ),
                    confidence=_safe_score(
                        item.get("confidence"),
                        1.0,
                    ),
                    entity_id=(
                        primary.id
                        if primary
                        else None
                    ),
                    source_note_id=note.id,
                    is_active=True,
                )
            )

            memory_count += 1

                # -----------------------------------------------------------
        # 7. Operational Tasks
        # -----------------------------------------------------------
        #
        # The main /ai/process endpoint already creates operational
        # tasks from ManagementData.
        #
        # When process_raw_note() is called from /ai/process,
        # create_operational_tasks=False prevents duplicate tasks.
        #
        # Direct secretary processing keeps the default behavior
        # and creates operational tasks normally.
        # -----------------------------------------------------------

        task_count = 0

        if create_operational_tasks:
            task_count = _create_operational_tasks(
                db=db,
                note=note,
                user_id=user_id,
                data=data,
                entity_map=entity_map,
            )
         
        # -----------------------------------------------------------
        # 8. Complete note
        # -----------------------------------------------------------

        note.processed = True
        note.processing_status = "completed"
        note.processed_at = datetime.utcnow()
        note.processing_error = None

        db.commit()

        return {
            "raw_note_id": note.id,
            "status": "completed",
            "entities": len(entity_map),
            "facts": fact_count,
            "relationships": relationship_count,
            "events": event_count,
            "memories": memory_count,
            "tasks": task_count,
        }

    except Exception as exc:
        db.rollback()

        # Re-fetch the note because rollback expires the in-memory state.
        fresh = (
            db.query(RawNote)
            .filter(RawNote.id == note.id)
            .first()
        )

        if fresh:
            fresh.processed = False
            fresh.processing_status = "failed"
            fresh.processing_error = (
                f"{type(exc).__name__}: {exc}"
            )

            db.commit()

        raise