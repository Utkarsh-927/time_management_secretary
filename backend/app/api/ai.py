from datetime import date, time, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database.database import get_db

from ..ai.parser import extract_information

from ..ai.commands import detect_command
from ..ai.command_executor import execute_command

from ..schemas.management import ManagementData

from ..services.reminder import process_reminders
from ..services.task_progress import process_task_progress

from ..services.time_budget_planner import (
    create_time_budget_plan,
    extract_available_minutes,
    is_time_budget_request,
)

from ..services.secretary_processor import process_raw_note

from ..models import (
    RawNote,
    Entity,
    Fact,
    EntityRelationship,
    Event,
    Memory,
)

from ..models.task import Task
from ..models.meeting import Meeting
from ..models.availability import Availability


PLANNING_HORIZON_DAYS = 30


router = APIRouter(
    prefix="/ai",
    tags=["AI Management"]
)


class AIMessageRequest(BaseModel):
    message: str
    user_id: str = "default"


# ============================================================
# DATE / TIME NORMALIZATION
# ============================================================

def normalize_date(value):
    """
    Convert AI-generated date values into Python date objects.

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

    try:
        return date.fromisoformat(value)

    except ValueError:
        pass

    return None


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


def normalize_datetime(
    value,
    fallback_date=None
):
    """
    Convert AI-generated datetime values into Python datetime objects.

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

    try:

        return datetime.fromisoformat(
            value
        )

    except ValueError:
        pass

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


def weekdays_from_message(
    message: str
):
    """
    Deterministically extract weekdays from
    the original user message.
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

    for raw_name, proper_name in (
        weekday_map.items()
    ):

        if raw_name in text:
            found.append(proper_name)

    if not found:
        return None

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

    if "every day" in message_lower:
        return "daily"

    if "each day" in message_lower:
        return "daily"

    if "daily" in message_lower:
        return "daily"

    if "every week" in message_lower:
        return "weekly"

    if "each week" in message_lower:
        return "weekly"

    if "weekly" in message_lower:
        return "weekly"

    if weekdays:
        return "weekly"

    if recurrence in (
        "daily",
        "weekly",
    ):
        return recurrence

    return "none"


# ============================================================
# SECRETARY QUESTION DETECTION
# ============================================================

def is_secretary_question(message: str) -> bool:
    """
    Detect questions that should be answered from stored
    personal-secretary memory rather than sent through the
    normal management extraction pipeline.
    """

    text = message.strip().lower()

    if not text:
        return False

    question_starts = (
        "what ",
        "when ",
        "where ",
        "who ",
        "whom ",
        "whose ",
        "which ",
        "how ",
        "did ",
        "do ",
        "does ",
        "can you ",
        "could you ",
        "tell me ",
        "show me ",
        "have i ",
        "what's ",
        "whats ",
    )

    looks_like_question = (
        "?" in text
        or text.startswith(question_starts)
    )

    if not looks_like_question:
        return False

    secretary_terms = (
        "project",
        "task",
        "assignment",
        "assigned",
        "responsible",
        "gave",
        "give",
        "budget",
        "deadline",
        "due",
        "review",
        "follow up",
        "follow-up",
        "meeting",
        "client",
        "person",
        "finish",
        "complete",
        "completed",
        "need to",
        "work on",
        "working on",
        "who did",
        "what did",
    )

    return any(
        term in text
        for term in secretary_terms
    )


# ============================================================
# SECRETARY MEMORY HELPERS
# ============================================================

def _secretary_fact_value(fact):
    """
    Get the actual typed value from a Fact.
    """

    if fact.value_type == "number":
        return fact.value_number

    if fact.value_type == "date":
        return fact.value_datetime

    if fact.value_type == "boolean":
        return fact.value_boolean

    if fact.value_type == "json":
        return fact.value_json

    return fact.value_text


def _secretary_text(value):
    """
    Safely convert a database value into text.
    """

    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _format_secretary_datetime(value):
    """
    Convert a datetime into a human-readable date.
    """

    if value is None:
        return ""

    if isinstance(value, datetime):

        return value.strftime(
            "%B %d, %Y"
        ).replace(" 0", " ")

    if isinstance(value, date):

        return value.strftime(
            "%B %d, %Y"
        ).replace(" 0", " ")

    text = str(value).strip()

    if not text:
        return ""

    try:

        parsed = datetime.fromisoformat(
            text.replace("Z", "")
        )

        return parsed.strftime(
            "%B %d, %Y"
        ).replace(" 0", " ")

    except ValueError:
        return text


def _clean_secretary_title(
    title,
    prefixes=()
):
    """
    Remove duplicated prefixes from stored event titles.
    """

    value = (
        str(title or "")
        .strip()
    )

    lower_value = value.lower()

    for prefix in prefixes:

        prefix_lower = prefix.lower()

        if lower_value.startswith(
            prefix_lower
        ):

            return value[
                len(prefix):
            ].strip()

    return value


def _find_secretary_entity(
    entities,
    name
):
    """
    Find an entity by exact or partial name.
    """

    if not name:
        return None

    target = str(
        name
    ).strip().lower()

    for entity in entities:

        entity_name = (
            getattr(
                entity,
                "name",
                ""
            )
            or ""
        ).strip().lower()

        if entity_name == target:
            return entity

    for entity in entities:

        entity_name = (
            getattr(
                entity,
                "name",
                ""
            )
            or ""
        ).strip().lower()

        if (
            target in entity_name
            or entity_name in target
        ):
            return entity

    return None


# ============================================================
# SECRETARY RETRIEVAL
# ============================================================

def _search_secretary_memory(
    question: str,
    user_id: str,
    db: Session,
):
    """
    Relationship-aware secretary retrieval.

    Example:

        What project did I give Arun?

    Retrieval:

        Arun
          |
          | responsible_for
          v
        ABC website project
          |
          +---- contains_task ---> homepage and contact form
          |
          +---- budget ---------> 25000 INR
          |
          +---- deadline -------> Friday
          |
          +---- review ----------> after 3 days
    """

    text = (
        question
        .strip()
        .lower()
    )

    # --------------------------------------------------------
    # 1. Extract useful words
    # --------------------------------------------------------

    words = [
        word.strip(
            ".,?!:;()[]{}\"'"
        )
        for word in text.split()
    ]

    stop_words = {
        "what",
        "when",
        "where",
        "who",
        "whom",
        "whose",
        "which",
        "why",
        "how",
        "did",
        "do",
        "does",
        "the",
        "a",
        "an",
        "i",
        "me",
        "my",
        "you",
        "your",
        "to",
        "for",
        "of",
        "on",
        "in",
        "is",
        "are",
        "was",
        "were",
        "and",
        "or",
        "give",
        "gave",
        "get",
        "got",
        "have",
        "has",
        "had",
        "need",
        "should",
        "can",
        "could",
        "would",
        "tell",
        "show",
    }

    useful_words = [
        word
        for word in words
        if (
            len(word) >= 2
            and word not in stop_words
        )
    ]

    # --------------------------------------------------------
    # 2. Load user's entities
    # --------------------------------------------------------

    all_entities = (
        db.query(Entity)
        .filter(
            Entity.user_id == user_id
        )
        .order_by(
            Entity.updated_at.desc()
        )
        .all()
    )

    if not all_entities:
        return (
            [],
            [],
            [],
            [],
            [],
        )

    # --------------------------------------------------------
    # 3. Direct entity matching
    # --------------------------------------------------------

    matched_entity_map = {}

    question_text = text

    for entity in all_entities:

        entity_name = (
            getattr(
                entity,
                "name",
                ""
            )
            or ""
        ).strip()

        if not entity_name:
            continue

        entity_name_lower = (
            entity_name.lower()
        )

        description = (
            getattr(
                entity,
                "description",
                ""
            )
            or ""
        ).lower()

        if entity_name_lower in question_text:

            matched_entity_map[
                entity.id
            ] = entity

            continue

        entity_words = [
            part
            for part in (
                entity_name_lower
                .replace("-", " ")
                .split()
            )
            if len(part) >= 2
        ]

        if any(
            part in useful_words
            for part in entity_words
        ):

            matched_entity_map[
                entity.id
            ] = entity

            continue

        if useful_words and any(
            word in description
            for word in useful_words
        ):

            matched_entity_map[
                entity.id
            ] = entity

    matched_entities = list(
        matched_entity_map.values()
    )

    # --------------------------------------------------------
    # 4. Fallback lexical DB search
    # --------------------------------------------------------

    if not matched_entities and useful_words:

        conditions = []

        for word in useful_words:

            conditions.append(
                Entity.name.ilike(
                    f"%{word}%"
                )
            )

            conditions.append(
                Entity.description.ilike(
                    f"%{word}%"
                )
            )

        matched_entities = (
            db.query(Entity)
            .filter(
                Entity.user_id == user_id,
                or_(*conditions),
            )
            .order_by(
                Entity.updated_at.desc()
            )
            .limit(30)
            .all()
        )

    # --------------------------------------------------------
    # 5. First relationship expansion
    # --------------------------------------------------------

    entity_ids = {
        entity.id
        for entity in matched_entities
    }

    relationship_base_query = (
        db.query(EntityRelationship)
        .filter(
            EntityRelationship.user_id
            == user_id,
            EntityRelationship.is_current.is_(True),
        )
    )

    relationships = []

    if entity_ids:

        relationships = (
            relationship_base_query
            .filter(
                or_(
                    EntityRelationship.source_entity_id.in_(
                        entity_ids
                    ),
                    EntityRelationship.target_entity_id.in_(
                        entity_ids
                    ),
                )
            )
            .order_by(
                EntityRelationship.created_at.desc()
            )
            .limit(100)
            .all()
        )

    connected_ids = set(
        entity_ids
    )

    for relationship in relationships:

        connected_ids.add(
            relationship.source_entity_id
        )

        connected_ids.add(
            relationship.target_entity_id
        )

    if connected_ids:

        connected_entities = (
            db.query(Entity)
            .filter(
                Entity.user_id == user_id,
                Entity.id.in_(
                    connected_ids
                ),
            )
            .all()
        )

        entity_map = {
            entity.id: entity
            for entity in matched_entities
        }

        for entity in connected_entities:

            entity_map[
                entity.id
            ] = entity

        matched_entities = list(
            entity_map.values()
        )

    # --------------------------------------------------------
    # 6. Second relationship expansion
    # --------------------------------------------------------

    expanded_ids = {
        entity.id
        for entity in matched_entities
    }

    if expanded_ids:

        relationships = (
            relationship_base_query
            .filter(
                or_(
                    EntityRelationship.source_entity_id.in_(
                        expanded_ids
                    ),
                    EntityRelationship.target_entity_id.in_(
                        expanded_ids
                    ),
                )
            )
            .order_by(
                EntityRelationship.created_at.desc()
            )
            .limit(150)
            .all()
        )

        second_level_ids = set(
            expanded_ids
        )

        for relationship in relationships:

            second_level_ids.add(
                relationship.source_entity_id
            )

            second_level_ids.add(
                relationship.target_entity_id
            )

        connected_entities = (
            db.query(Entity)
            .filter(
                Entity.user_id == user_id,
                Entity.id.in_(
                    second_level_ids
                ),
            )
            .all()
        )

        entity_map = {
            entity.id: entity
            for entity in matched_entities
        }

        for entity in connected_entities:

            entity_map[
                entity.id
            ] = entity

        matched_entities = list(
            entity_map.values()
        )

    # --------------------------------------------------------
    # 7. If no entity was found, use recent entities
    # --------------------------------------------------------

    if not matched_entities:

        matched_entities = (
            db.query(Entity)
            .filter(
                Entity.user_id == user_id
            )
            .order_by(
                Entity.updated_at.desc()
            )
            .limit(20)
            .all()
        )

    entity_ids = {
        entity.id
        for entity in matched_entities
    }

    # --------------------------------------------------------
    # 8. Facts
    # --------------------------------------------------------

    fact_query = (
        db.query(Fact)
        .filter(
            Fact.user_id == user_id,
            Fact.is_current.is_(True),
        )
    )

    if entity_ids:

        facts = (
            fact_query
            .filter(
                Fact.entity_id.in_(
                    entity_ids
                )
            )
            .order_by(
                Fact.updated_at.desc()
            )
            .limit(100)
            .all()
        )

    else:

        facts = (
            fact_query
            .order_by(
                Fact.updated_at.desc()
            )
            .limit(50)
            .all()
        )

    # --------------------------------------------------------
    # 9. Relationships
    # --------------------------------------------------------

    if entity_ids:

        relationships = (
            relationship_base_query
            .filter(
                or_(
                    EntityRelationship.source_entity_id.in_(
                        entity_ids
                    ),
                    EntityRelationship.target_entity_id.in_(
                        entity_ids
                    ),
                )
            )
            .order_by(
                EntityRelationship.created_at.desc()
            )
            .limit(150)
            .all()
        )

    else:

        relationships = (
            relationship_base_query
            .order_by(
                EntityRelationship.created_at.desc()
            )
            .limit(50)
            .all()
        )

    # --------------------------------------------------------
    # 10. Events
    # --------------------------------------------------------

    event_query = (
        db.query(Event)
        .filter(
            Event.user_id == user_id
        )
    )

    if entity_ids:

        events = (
            event_query
            .filter(
                Event.primary_entity_id.in_(
                    entity_ids
                )
            )
            .order_by(
                Event.event_time.asc(),
                Event.created_at.desc(),
            )
            .limit(100)
            .all()
        )

    else:

        events = (
            event_query
            .order_by(
                Event.event_time.asc(),
                Event.created_at.desc(),
            )
            .limit(50)
            .all()
        )

    # --------------------------------------------------------
    # 11. Memories
    # --------------------------------------------------------

    memory_query = (
        db.query(Memory)
        .filter(
            Memory.user_id == user_id,
            Memory.is_active.is_(True),
        )
    )

    if entity_ids:

        memories = (
            memory_query
            .filter(
                Memory.entity_id.in_(entity_ids)
            )
            .order_by(
                Memory.importance.desc(),
                Memory.updated_at.desc(),
            )
            .limit(100)
            .all()
        )

    else:

        memories = (
            memory_query
            .order_by(
                Memory.importance.desc(),
                Memory.updated_at.desc(),
            )
            .limit(50)
            .all()
        )

    return (
        matched_entities,
        facts,
        relationships,
        events,
        memories,
    )


# ============================================================
# DETERMINISTIC SECRETARY ANSWER
# ============================================================

def _deterministic_secretary_answer(
    question: str,
    entities,
    facts,
    relationships,
    events,
    memories,
) -> str | None:
    """
    Answer common secretary questions directly from
    structured memory.

    Deterministic answers are preferred over Gemma for
    simple factual retrieval.
    """

    text = (
        question or ""
    ).strip().lower()

    # ---------------------------------------------------------
    # Build lookup maps
    # ---------------------------------------------------------

    entity_names = {
        entity.id: (
            getattr(
                entity,
                "name",
                ""
            ) or ""
        )
        for entity in entities
    }

    entity_types = {
        entity.id: (
            getattr(
                entity,
                "entity_type",
                ""
            ) or ""
        ).upper()
        for entity in entities
    }

    # ---------------------------------------------------------
    # Extract person mentioned in the question
    # ---------------------------------------------------------

    question_words = [
        word.strip(
            ".,?!:;()[]{}\"'"
        )
        for word in text.split()
    ]

    mentioned_person = None

    for entity in entities:

        if (
            getattr(
                entity,
                "entity_type",
                ""
            ) != "PERSON"
        ):
            continue

        name = (
            getattr(
                entity,
                "name",
                ""
            ) or ""
        ).strip()

        if not name:
            continue

        if name.lower() in question_words:

            mentioned_person = entity

            break

    # ---------------------------------------------------------
    # 1. PROJECT ASSIGNMENT QUESTIONS
    #
    # Examples:
    #
    # What project did I give Arun?
    # What did I assign Arun?
    # Which project did I assign to Arun?
    # What project is Arun handling?
    # ---------------------------------------------------------

    assignment_question = (
        "project" in text
        or "assign" in text
        or "assigned" in text
        or "gave" in text
        or "give" in text
        or "handling" in text
        or "handle" in text
    )

    if (
        assignment_question
        and mentioned_person is not None
    ):

        for relationship in relationships:

            if (
                relationship.source_entity_id
                != mentioned_person.id
            ):
                continue

            relationship_type = (
                getattr(
                    relationship,
                    "relationship_type",
                    ""
                ) or ""
            ).lower()

            target_id = (
                relationship.target_entity_id
            )

            target_name = entity_names.get(
                target_id
            )

            target_type = entity_types.get(
                target_id,
                ""
            )

            if not target_name:
                continue

            is_assignment_relationship = (
                "responsible" in relationship_type
                or "assigned" in relationship_type
                or "owner" in relationship_type
            )

            if not is_assignment_relationship:
                continue

            if target_type == "PROJECT":

                return (
                    f"You gave "
                    f"{mentioned_person.name} "
                    f"the {target_name}."
                )

    # ---------------------------------------------------------
    # 2. PERSON'S TASK / WORK QUESTIONS
    #
    # Important:
    #
    # The database may store:
    #
    # Arun
    #   ↓ responsible_for
    # ABC website project
    #   ↓ contains_task
    # homepage and contact form
    #
    # Therefore we must follow the relationship chain.
    # ---------------------------------------------------------

    person_task_question = (
        "task" in text
        or "work" in text
        or "finish" in text
        or "finished" in text
        or "complete" in text
        or "completed" in text
        or "need to" in text
        or "get" in text
        or "got" in text
    )

    if (
        person_task_question
        and mentioned_person is not None
    ):

        person_project_ids = set()

        # -----------------------------------------------------
        # Step A:
        # Find projects assigned to this person.
        # -----------------------------------------------------

        for relationship in relationships:

            if (
                relationship.source_entity_id
                != mentioned_person.id
            ):
                continue

            relationship_type = (
                getattr(
                    relationship,
                    "relationship_type",
                    ""
                ) or ""
            ).lower()

            target_id = (
                relationship.target_entity_id
            )

            target_type = entity_types.get(
                target_id,
                ""
            )

            if target_type != "PROJECT":
                continue

            is_project_assignment = (
                "responsible" in relationship_type
                or "assigned" in relationship_type
                or "owner" in relationship_type
            )

            if is_project_assignment:

                person_project_ids.add(
                    target_id
                )

        # -----------------------------------------------------
        # Step B:
        # Find tasks contained in those projects.
        # -----------------------------------------------------

        person_task_names = []

        for relationship in relationships:

            source_id = (
                relationship.source_entity_id
            )

            target_id = (
                relationship.target_entity_id
            )

            if source_id not in person_project_ids:
                continue

            relationship_type = (
                getattr(
                    relationship,
                    "relationship_type",
                    ""
                ) or ""
            ).lower()

            target_type = entity_types.get(
                target_id,
                ""
            )

            if target_type != "TASK":
                continue

            is_task_relationship = (
                "task" in relationship_type
                or "contain" in relationship_type
                or "include" in relationship_type
            )

            if not is_task_relationship:
                continue

            task_name = entity_names.get(
                target_id
            )

            if task_name:

                person_task_names.append(
                    task_name
                )

        # -----------------------------------------------------
        # Step C:
        # Direct PERSON -> TASK fallback.
        # -----------------------------------------------------

        if not person_task_names:

            for relationship in relationships:

                if (
                    relationship.source_entity_id
                    != mentioned_person.id
                ):
                    continue

                relationship_type = (
                    getattr(
                        relationship,
                        "relationship_type",
                        ""
                    ) or ""
                ).lower()

                target_id = (
                    relationship.target_entity_id
                )

                target_type = entity_types.get(
                    target_id,
                    ""
                )

                if target_type != "TASK":
                    continue

                is_direct_task_relationship = (
                    "task" in relationship_type
                    or "assigned" in relationship_type
                    or "responsible" in relationship_type
                    or "work" in relationship_type
                )

                if not is_direct_task_relationship:
                    continue

                task_name = entity_names.get(
                    target_id
                )

                if task_name:

                    person_task_names.append(
                        task_name
                    )

        # -----------------------------------------------------
        # Step D:
        # Fallback to task descriptions.
        # -----------------------------------------------------

        if not person_task_names:

            person_name = (
                getattr(
                    mentioned_person,
                    "name",
                    ""
                ) or ""
            ).lower()

            for entity in entities:

                if (
                    getattr(
                        entity,
                        "entity_type",
                        ""
                    ) != "TASK"
                ):
                    continue

                description = (
                    getattr(
                        entity,
                        "description",
                        ""
                    ) or ""
                ).lower()

                if (
                    person_name
                    and person_name in description
                ):

                    task_name = (
                        getattr(
                            entity,
                            "name",
                            ""
                        ) or ""
                    )

                    if task_name:

                        person_task_names.append(
                            task_name
                        )

        # -----------------------------------------------------
        # Remove duplicates.
        # -----------------------------------------------------

        person_task_names = list(
            dict.fromkeys(
                person_task_names
            )
        )

        # -----------------------------------------------------
        # Return person-specific answer.
        # -----------------------------------------------------

        if person_task_names:

            if len(person_task_names) == 1:

                return (
                    f"{mentioned_person.name} "
                    f"needs to finish "
                    f"{person_task_names[0]}."
                )

            if len(person_task_names) == 2:

                return (
                    f"{mentioned_person.name} "
                    f"needs to finish "
                    f"{person_task_names[0]} "
                    f"and "
                    f"{person_task_names[1]}."
                )

            return (
                f"{mentioned_person.name} "
                f"needs to finish "
                + ", ".join(
                    person_task_names[:-1]
                )
                + ", and "
                + person_task_names[-1]
                + "."
            )

    # ---------------------------------------------------------
    # 3. RESPONSIBILITY QUESTIONS
    #
    # Examples:
    #
    # What is Arun responsible for?
    # Who is responsible for the ABC website project?
    # ---------------------------------------------------------

    if (
        "responsible" in text
        or "assigned to" in text
        or "who is handling" in text
    ):

        for relationship in relationships:

            relationship_type = (
                getattr(
                    relationship,
                    "relationship_type",
                    ""
                ) or ""
            ).lower()

            if not (
                "responsible" in relationship_type
                or "assigned" in relationship_type
                or "owner" in relationship_type
            ):
                continue

            source_name = entity_names.get(
                relationship.source_entity_id
            )

            target_name = entity_names.get(
                relationship.target_entity_id
            )

            if source_name and target_name:

                return (
                    f"{source_name} "
                    f"is responsible for "
                    f"{target_name}."
                )

    # ---------------------------------------------------------
    # 4. BUDGET / COST QUESTIONS
    # ---------------------------------------------------------

    if (
        "budget" in text
        or "cost" in text
        or "price" in text
        or "amount" in text
    ):

        for fact in facts:

            key = (
                getattr(
                    fact,
                    "key",
                    ""
                ) or ""
            ).lower()

            if key not in {
                "budget",
                "cost",
                "price",
                "amount",
            }:
                continue

            entity_name = entity_names.get(
                getattr(
                    fact,
                    "entity_id",
                    None
                )
            )

            value = _secretary_fact_value(
                fact
            )

            unit = (
                getattr(
                    fact,
                    "unit",
                    None
                )
                or ""
            ).strip()

            if (
                entity_name
                and value is not None
            ):

                if unit:

                    return (
                        f"The {key} for "
                        f"{entity_name} is "
                        f"{value} {unit}."
                    )

                return (
                    f"The {key} for "
                    f"{entity_name} is "
                    f"{value}."
                )

    # ---------------------------------------------------------
    # 5. DEADLINE QUESTIONS
    # ---------------------------------------------------------

    if (
        "deadline" in text
        or "due" in text
        or "when" in text
    ):

        for event in events:

            event_type = (
                getattr(
                    event,
                    "event_type",
                    ""
                ) or ""
            ).upper()

            if event_type != "DEADLINE":
                continue

            title = (
                getattr(
                    event,
                    "title",
                    ""
                ) or ""
            ).strip()

            event_time = getattr(
                event,
                "event_time",
                None
            )

            entity_name = entity_names.get(
                getattr(
                    event,
                    "primary_entity_id",
                    None
                )
            )

            if (
                entity_name
                and event_time
            ):

                return (
                    f"The {entity_name} "
                    f"is due "
                    f"{_format_secretary_datetime(event_time)}."
                )

            if (
                entity_name
                and title
            ):

                return (
                    f"The deadline for "
                    f"{entity_name} is "
                    f"{title}."
                )

    # ---------------------------------------------------------
    # 6. REVIEW / FOLLOW-UP QUESTIONS
    # ---------------------------------------------------------

    if (
        "review" in text
        or "follow up" in text
        or "follow-up" in text
    ):

        for event in events:

            event_type = (
                getattr(
                    event,
                    "event_type",
                    ""
                ) or ""
            ).upper()

            if event_type not in {
                "REVIEW",
                "FOLLOW_UP",
            }:
                continue

            entity_name = entity_names.get(
                getattr(
                    event,
                    "primary_entity_id",
                    None
                )
            )

            event_time = getattr(
                event,
                "event_time",
                None
            )

            if (
                entity_name
                and event_time
            ):

                return (
                    f"You should review "
                    f"the {entity_name} "
                    f"after 3 days on "
                    f"{_format_secretary_datetime(event_time)}."
                )

            if entity_name:

                return (
                    f"You should review "
                    f"the {entity_name}."
                )

    # ---------------------------------------------------------
    # 7. GENERAL TASK QUESTIONS
    #
    # This is intentionally AFTER person-specific task
    # handling so:
    #
    #   What task did Arun get?
    #
    # does not become:
    #
    #   You need to work on ...
    # ---------------------------------------------------------

    if (
        "task" in text
        or "what do i need to" in text
        or "what should i" in text
    ):

        task_entities = [
            entity
            for entity in entities
            if (
                getattr(
                    entity,
                    "entity_type",
                    ""
                ) == "TASK"
            )
        ]

        if task_entities:

            task_names = [
                getattr(
                    entity,
                    "name",
                    ""
                )
                for entity in task_entities
                if getattr(
                    entity,
                    "name",
                    ""
                )
            ]

            if len(task_names) == 1:

                return (
                    f"You need to work on "
                    f"{task_names[0]}."
                )

            if task_names:

                return (
                    "Your tasks are: "
                    + ", ".join(task_names)
                    + "."
                )

    # ---------------------------------------------------------
    # Nothing matched.
    # Let Gemma handle more complex questions.
    # ---------------------------------------------------------

    return None


# ============================================================
# SECRETARY GROUNDED ANSWER
# ============================================================

def _run_secretary_retrieval(
    question,
    user_id,
    db,
):
    """
    Retrieve secretary memory and answer the question.

    Deterministic structured answers are preferred.

    Gemma is used only when a deterministic answer
    cannot be produced.
    """

    from .secretary import (
        _build_grounded_context,
        _run_secretary_answer,
    )

    (
        entities,
        facts,
        relationships,
        events,
        memories,
    ) = _search_secretary_memory(
        question=question,
        user_id=user_id,
        db=db,
    )

    deterministic_answer = (
        _deterministic_secretary_answer(
            question=question,
            entities=entities,
            facts=facts,
            relationships=relationships,
            events=events,
            memories=memories,
        )
    )

    if deterministic_answer:

        return {
            "answer": deterministic_answer,

            "sources": {
                "entities": len(
                    entities
                ),
                "facts": len(
                    facts
                ),
                "relationships": len(
                    relationships
                ),
                "events": len(
                    events
                ),
                "memories": len(
                    memories
                ),
            },

            "entities": entities,
            "facts": facts,
            "relationships": relationships,
            "events": events,
            "memories": memories,
        }

    context = _build_grounded_context(
        entities=entities,
        facts=facts,
        relationships=relationships,
        events=events,
        memories=memories,
    )

    answer = _run_secretary_answer(
        question=question,
        context=context,
    )

    return {
        "answer": answer,

        "sources": {
            "entities": len(
                entities
            ),
            "facts": len(
                facts
            ),
            "relationships": len(
                relationships
            ),
            "events": len(
                events
            ),
            "memories": len(
                memories
            ),
        },

        "entities": entities,
        "facts": facts,
        "relationships": relationships,
        "events": events,
        "memories": memories,
    }


# ============================================================
# AI PROCESSING
# ============================================================

@router.post("/process")
def process_message(
    request: AIMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Process a natural-language message.

    Supported paths:

    1. Management commands
       -> update/delete/create reminder

    2. Natural-language secretary questions
       -> retrieve stored secretary memory

    3. Natural-language time planning
       -> "I have 20 minutes. What should I do?"

    4. Task progress updates
       -> worked X minutes
       -> completed/finished task

    5. Normal AI extraction
       -> create tasks, meetings,
          availability and reminders

    6. Personal secretary memory capture
       -> store raw note
       -> extract entities/facts/
          relationships/events/memories
    """

    message = request.message.strip()

    user_id = (
        request.user_id
        or "default"
    )

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    # ========================================================
    # 1. COMMAND DETECTION
    # ========================================================

    try:

        command = detect_command(
            message
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
    # 2. MANAGEMENT COMMAND
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

            "task_progress": None,

            "time_planning": None,

            "secretary": None,
        }

    # ========================================================
    # 3. PERSONAL SECRETARY QUESTION
    # ========================================================

    if is_secretary_question(message):

        try:

            secretary_answer = (
                _run_secretary_retrieval(
                    question=message,
                    user_id=user_id,
                    db=db,
                )
            )

            print(
                "\n========== SECRETARY RETRIEVAL =========="
            )

            print(
                secretary_answer.get(
                    "sources",
                    {}
                )
            )

            print(
                "Answer:",
                secretary_answer.get(
                    "answer"
                )
            )

            print(
                "==========================================\n"
            )

            return {
                "message": secretary_answer.get(
                    "answer",
                    "I don't have that information in my memory."
                ),

                "command_processed": False,

                "time_planning": None,

                "task_progress": None,

                "extracted_data": {
                    "tasks": [],
                    "meetings": [],
                    "availability": [],
                    "reminders": [],
                },

                "created": {
                    "tasks": 0,
                    "meetings": 0,
                    "availability": 0,
                    "reminders": 0,
                },

                "duplicates": {
                    "tasks": []
                },

                "secretary": {
                    "status": "answered",

                    "question": message,

                    "answer": secretary_answer.get(
                        "answer"
                    ),

                    "sources": secretary_answer.get(
                        "sources",
                        {}
                    ),
                },
            }

        except Exception as error:

            db.rollback()

            import traceback

            traceback.print_exc()

            print(
                "Secretary retrieval failed."
            )

            return {
                "message": (
                    "I could not retrieve that information "
                    "from your secretary memory."
                ),

                "command_processed": False,

                "time_planning": None,

                "task_progress": None,

                "extracted_data": {
                    "tasks": [],
                    "meetings": [],
                    "availability": [],
                    "reminders": [],
                },

                "created": {
                    "tasks": 0,
                    "meetings": 0,
                    "availability": 0,
                    "reminders": 0,
                },

                "duplicates": {
                    "tasks": []
                },

                "secretary": {
                    "status": "failed",

                    "error": (
                        f"{type(error).__name__}: {error}"
                    ),
                },
            }

    # ========================================================
    # 4. NATURAL-LANGUAGE TIME PLANNING
    # ========================================================

    try:

        if is_time_budget_request(message):

            available_minutes = (
                extract_available_minutes(
                    message
                )
            )

            if available_minutes is not None:

                tasks = (
                    db.query(Task)
                    .filter(
                        Task.user_id == user_id
                    )
                    .all()
                )

                time_plan = (
                    create_time_budget_plan(
                        tasks=tasks,
                        available_minutes=(
                            available_minutes
                        ),
                    )
                )

                recommendations = (
                    time_plan.get(
                        "recommendations",
                        []
                    )
                )

                if recommendations:

                    parts = []

                    for recommendation in (
                        recommendations
                    ):

                        title = (
                            recommendation.get(
                                "task_title",
                                "Unnamed task"
                            )
                        )

                        minutes = int(
                            recommendation.get(
                                "recommended_minutes",
                                0
                            )
                            or 0
                        )

                        partial = bool(
                            recommendation.get(
                                "partial",
                                False
                            )
                        )

                        if partial:

                            parts.append(
                                f"'{title}' "
                                f"for {minutes} minutes "
                                f"(partial progress)"
                            )

                        else:

                            parts.append(
                                f"'{title}' "
                                f"for {minutes} minutes"
                            )

                    if len(parts) == 1:

                        answer = (
                            f"You have "
                            f"{available_minutes} minutes. "
                            f"I recommend working on "
                            f"{parts[0]}."
                        )

                    else:

                        answer = (
                            f"You have "
                            f"{available_minutes} minutes. "
                            f"I recommend: "
                            + "; ".join(parts)
                            + "."
                        )

                else:

                    answer = time_plan.get(
                        "message",
                        (
                            "There are no suitable "
                            "active tasks for this "
                            "time budget."
                        )
                    )

                print(
                    "\n========== TIME BUDGET PLANNER =========="
                )

                print(
                    time_plan
                )

                print(
                    "=========================================\n"
                )

                return {
                    "message": answer,

                    "command_processed": False,

                    "time_planning": {
                        "available_minutes": (
                            available_minutes
                        ),
                        "plan": time_plan,
                    },

                    "task_progress": None,

                    "extracted_data": {
                        "tasks": [],
                        "meetings": [],
                        "availability": [],
                        "reminders": [],
                    },

                    "created": {
                        "tasks": 0,
                        "meetings": 0,
                        "availability": 0,
                        "reminders": 0,
                    },

                    "duplicates": {
                        "tasks": []
                    },

                    "secretary": None,
                }

    except Exception as error:

        db.rollback()

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Time-budget planning failed: "
                f"{type(error).__name__}: {error}"
            )
        )

    # ========================================================
    # 5. TASK PROGRESS PROCESSING
    # ========================================================

    try:

        task_progress = process_task_progress(
            db=db,
            user_id=user_id,
            message=message,
        )

        print(
            "\n========== TASK PROGRESS =========="
        )

        print(task_progress)

        print(
            "===================================\n"
        )

    except Exception as error:

        db.rollback()

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Task progress processing failed: "
                f"{type(error).__name__}: {error}"
            )
        )

    if (
        task_progress
        and task_progress.get("success")
    ):

        return {
            "message": task_progress.get(
                "message",
                "Task progress updated."
            ),

            "command_processed": False,

            "time_planning": None,

            "task_progress": task_progress,

            "extracted_data": {
                "tasks": [],
                "meetings": [],
                "availability": [],
                "reminders": [],
            },

            "created": {
                "tasks": 0,
                "meetings": 0,
                "availability": 0,
                "reminders": 0,
            },

            "duplicates": {
                "tasks": []
            },

            "secretary": None,
        }

    # ========================================================
    # 6. NORMAL AI EXTRACTION
    # ========================================================

    try:

        raw_data = extract_information(
            message
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
    # 7. VALIDATE AI DATA
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

    message_date = get_message_date(
        message
    )

    # ========================================================
    # 8. CREATE TASKS
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

        task_title = (
            task_data.title or ""
        ).strip()

        normalized_title = (
            task_title.lower()
        )

        existing_tasks = (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
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

            if (
                normalized_title
                == existing_title
            ):

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

                if same_deadline:

                    duplicate = (
                        existing_task
                    )

                    break

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

        task = Task(
            user_id=user_id,
            title=task_data.title,
            description=task_data.description,
            deadline=deadline,
            estimated_duration=(
                task_data.estimated_duration
            ),
            remaining_duration=(
                task_data.estimated_duration
            ),
            importance=task_data.importance,
            progress_percent=0,
            urgency=3,
            priority_score=0.0,
            status="pending",
        )

        db.add(task)

        created_tasks.append(
            task
        )

    # ========================================================
    # 9. CREATE MEETINGS
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
            user_id=user_id,
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
    # 10. CREATE AVAILABILITY
    # ========================================================

    created_availability = []

    for availability_data in data.availability:

        start_date = normalize_date(
            availability_data.start_date
        )

        end_date = normalize_date(
            availability_data.end_date
        )

        start_time = normalize_time(
            availability_data.start_time
        )

        end_time = normalize_time(
            availability_data.end_time
        )

        message_weekdays = (
            weekdays_from_message(
                message
            )
        )

        weekdays = normalize_weekdays(
            availability_data.weekdays
        )

        if message_weekdays:

            weekdays = ",".join(
                message_weekdays
            )

        recurrence = normalize_recurrence(
            availability_data.recurrence,
            message,
            message_weekdays
            or availability_data.weekdays
        )

        if start_date is None:

            start_date = message_date

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

        else:

            if end_date is None:

                end_date = start_date

            weekdays = None

        if (
            start_time is None
            or end_time is None
        ):
            continue

        if start_time >= end_time:
            continue

        if recurrence == "weekly":

            if not weekdays:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Weekly availability requires "
                        "at least one weekday."
                    )
                )

        if recurrence == "daily":

            weekdays = None

        availability = Availability(
            user_id=user_id,
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
    # 11. COMMIT TASKS / MEETINGS / AVAILABILITY
    # ========================================================

    created_reminders = []

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
    # 12. REFRESH MEETINGS
    # ========================================================

    for meeting in created_meetings:

        db.refresh(
            meeting
        )

    # ========================================================
    # 13. PROCESS REMINDERS
    # ========================================================

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
    # 14. COMMIT REMINDERS
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
                f"Database error: "
                f"{error}"
            )
        )

    # ========================================================
    # 15. PERSONAL SECRETARY MEMORY CAPTURE
    # ========================================================

    secretary_result = None

    try:

        secretary_note = RawNote(
            user_id=user_id,
            raw_text=message,
            source="ai_process",
            processed=False,
            processing_status="pending",
        )

        db.add(
            secretary_note
        )

        db.commit()

        db.refresh(
            secretary_note
        )

        secretary_result = process_raw_note(
            db=db,
            note=secretary_note,
            user_id=user_id,
            create_operational_tasks=False,
        )

        print(
            "\n========== SECRETARY MEMORY =========="
        )

        print(
            secretary_result
        )

        print(
            "=======================================\n"
        )

    except Exception as error:

        import traceback

        traceback.print_exc()

        secretary_result = {
            "status": "failed",
            "error": (
                f"{type(error).__name__}: {error}"
            ),
        }

        try:

            db.rollback()

        except Exception:
            pass

    # ========================================================
    # 16. REFRESH CREATED OBJECTS
    # ========================================================

    for task in created_tasks:

        db.refresh(
            task
        )

    for meeting in created_meetings:

        db.refresh(
            meeting
        )

    for availability in created_availability:

        db.refresh(
            availability
        )

    for reminder in created_reminders:

        db.refresh(
            reminder
        )

    # ========================================================
    # 17. FINAL RESPONSE
    # ========================================================
    print("\n========== FINAL DATA DUMP ==========")
    print(data.model_dump())
    print("=====================================\n")
    return {
        "message": (
            "Message processed successfully"
        ),

        "command_processed": False,

        "time_planning": None,

        "task_progress": task_progress,

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
        },

        "secretary": secretary_result,
    }