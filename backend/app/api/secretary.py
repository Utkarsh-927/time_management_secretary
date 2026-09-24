from datetime import datetime
from typing import Optional

import os
import re
import subprocess
import tempfile

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database.database import get_db

from ..models import (
    RawNote,
    ConversationMessage,
    Entity,
    Fact,
    EntityRelationship,
    Event,
    Memory,
)

from ..models.task import Task

from ..services.time_budget_planner import (
    create_time_budget_plan,
)


router = APIRouter(
    prefix="/ai/secretary",
    tags=["AI Secretary"],
)


# ============================================================================
# Existing endpoints
# ============================================================================


@router.get("/notes")
def list_notes(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = "default",
    db: Session = Depends(get_db),
):
    """
    Return stored raw secretary notes.
    """

    notes = (
        db.query(RawNote)
        .filter(RawNote.user_id == user_id)
        .order_by(RawNote.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": note.id,
            "raw_text": note.raw_text,
            "source": note.source,
            "conversation_id": note.conversation_id,
            "processed": note.processed,
            "processing_status": note.processing_status,
            "processing_error": note.processing_error,
            "created_at": note.created_at,
        }
        for note in notes
    ]


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """
    Return messages belonging to a secretary conversation.
    """

    messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id
            == conversation_id
        )
        .order_by(
            ConversationMessage.created_at.asc()
        )
        .all()
    )

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in messages
    ]


@router.get("/knowledge")
def secretary_knowledge(
    user_id: str = "default",
    db: Session = Depends(get_db),
):
    """
    Return all structured secretary knowledge.

    This endpoint is mainly useful for verification/debugging.
    """

    entities = (
        db.query(Entity)
        .filter(Entity.user_id == user_id)
        .order_by(Entity.created_at.asc())
        .all()
    )

    entity_by_id = {
        entity.id: entity.name
        for entity in entities
    }

    facts = (
        db.query(Fact)
        .filter(Fact.user_id == user_id)
        .order_by(Fact.created_at.asc())
        .all()
    )

    relationships = (
        db.query(EntityRelationship)
        .filter(
            EntityRelationship.user_id == user_id,
            EntityRelationship.is_current.is_(True),
        )
        .order_by(
            EntityRelationship.created_at.asc()
        )
        .all()
    )

    events = (
        db.query(Event)
        .filter(Event.user_id == user_id)
        .order_by(Event.created_at.asc())
        .all()
    )

    memories = (
        db.query(Memory)
        .filter(
            Memory.user_id == user_id,
            Memory.is_active.is_(True),
        )
        .order_by(Memory.created_at.asc())
        .all()
    )

    def fact_value(fact):
        if fact.value_type == "number":
            return fact.value_number

        if fact.value_type == "date":
            return fact.value_datetime

        if fact.value_type == "boolean":
            return fact.value_boolean

        if fact.value_type == "json":
            return fact.value_json

        return fact.value_text

    return {
        "entities": [
            {
                "id": entity.id,
                "type": entity.entity_type,
                "name": entity.name,
                "description": entity.description,
            }
            for entity in entities
        ],

        "facts": [
            {
                "id": fact.id,
                "entity": entity_by_id.get(
                    fact.entity_id
                ),
                "key": fact.key,
                "value": fact_value(fact),
                "value_type": fact.value_type,
                "unit": fact.unit,
                "confidence": fact.confidence,
                "source_note_id": fact.source_note_id,
                "is_current": fact.is_current,
            }
            for fact in facts
        ],

        "relationships": [
            {
                "id": relationship.id,
                "source": entity_by_id.get(
                    relationship.source_entity_id
                ),
                "relationship_type": (
                    relationship.relationship_type
                ),
                "target": entity_by_id.get(
                    relationship.target_entity_id
                ),
                "confidence": relationship.confidence,
                "source_note_id": (
                    relationship.source_note_id
                ),
            }
            for relationship in relationships
        ],

        "events": [
            {
                "id": event.id,
                "type": event.event_type,
                "title": event.title,
                "description": event.description,
                "event_time": event.event_time,
                "end_time": event.end_time,
                "primary_entity": entity_by_id.get(
                    event.primary_entity_id
                ),
                "source_note_id": (
                    event.source_note_id
                ),
            }
            for event in events
        ],

        "memories": [
            {
                "id": memory.id,
                "type": memory.memory_type,
                "content": memory.content,
                "importance": memory.importance,
                "confidence": memory.confidence,
                "entity": entity_by_id.get(
                    memory.entity_id
                ),
                "source_note_id": (
                    memory.source_note_id
                ),
            }
            for memory in memories
        ],
    }


# ============================================================================
# Natural-language secretary retrieval
# ============================================================================


class SecretaryAskRequest(BaseModel):
    question: str
    user_id: str = "default"


def _fact_value(fact: Fact):
    """
    Return the actual typed value stored in a Fact.
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


def _safe_text(value) -> str:
    """
    Convert database values into safe prompt text.
    """

    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


# ============================================================================
# Time-budget detection
# ============================================================================


def _parse_time_budget(
    question: str,
) -> Optional[int]:
    """
    Detect available time from natural language.

    Supported examples:
        I have 20 minutes
        I have 1 hour
        I have 3 hours
        I have 90 minutes
        I have 1.5 hours
        I have an hour
        I only have 30 mins
        I have half an hour

    Returns:
        available minutes, or None when no time budget
        is detected.
    """

    q = question.lower().strip()

    # ------------------------------------------------------------------
    # Common natural-language expressions
    # ------------------------------------------------------------------

    if re.search(
        r"\bhalf\s+an?\s+hour\b",
        q,
    ):
        return 30

    if re.search(
        r"\ban?\s+hour\b",
        q,
    ):
        return 60

    # ------------------------------------------------------------------
    # Decimal hours
    # ------------------------------------------------------------------

    decimal_hour_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:hours?|hrs?|hr)\b",
        q,
        flags=re.IGNORECASE,
    )

    if decimal_hour_match:
        try:
            hours = float(
                decimal_hour_match.group(1)
            )

            minutes = round(
                hours * 60
            )

            if minutes > 0:
                return minutes

        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------
    # Minutes
    # ------------------------------------------------------------------

    minute_match = re.search(
        r"\b(\d+)\s*"
        r"(?:minutes?|mins?|min)\b",
        q,
        flags=re.IGNORECASE,
    )

    if minute_match:
        try:
            minutes = int(
                minute_match.group(1)
            )

            if minutes > 0:
                return minutes

        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------
    # Integer hours
    # ------------------------------------------------------------------

    hour_match = re.search(
        r"\b(\d+)\s*"
        r"(?:hours?|hrs?|hr)\b",
        q,
        flags=re.IGNORECASE,
    )

    if hour_match:
        try:
            hours = int(
                hour_match.group(1)
            )

            minutes = hours * 60

            if minutes > 0:
                return minutes

        except (TypeError, ValueError):
            pass

    return None


def _is_time_budget_question(
    question: str,
) -> bool:
    """
    Determine whether the user's message is asking
    what work they can do within a limited amount of time.

    A duration alone is not enough.

    For example:
        "The meeting lasts 2 hours"

    should not automatically become a planning request.

    The question should also contain planning/work intent.
    """

    minutes = _parse_time_budget(
        question
    )

    if minutes is None:
        return False

    q = question.lower().strip()

    planning_phrases = (
        "i have",
        "i've got",
        "ive got",
        "i got",
        "i only have",
        "i only got",
        "i can work",
        "what should i do",
        "what can i do",
        "what should i work on",
        "what can i work on",
        "what task should i do",
        "what task can i do",
        "help me plan",
        "plan my time",
        "use my time",
        "available time",
        "free time",
        "time available",
        "work for",
    )

    return any(
        phrase in q
        for phrase in planning_phrases
    )


def _format_duration(
    minutes: int,
) -> str:
    """
    Convert minutes into natural-language duration.
    """

    minutes = max(
        0,
        int(minutes),
    )

    if minutes == 0:
        return "0 minutes"

    if minutes < 60:
        return (
            f"{minutes} minute"
            if minutes == 1
            else f"{minutes} minutes"
        )

    hours = minutes // 60
    remainder = minutes % 60

    if remainder == 0:
        return (
            f"{hours} hour"
            if hours == 1
            else f"{hours} hours"
        )

    hour_text = (
        f"{hours} hour"
        if hours == 1
        else f"{hours} hours"
    )

    minute_text = (
        f"{remainder} minute"
        if remainder == 1
        else f"{remainder} minutes"
    )

    return f"{hour_text} {minute_text}"


# ============================================================================
# Time-budget response
# ============================================================================


def _build_time_budget_answer(
    plan: dict,
) -> str:
    """
    Convert the structured time-budget plan into a
    natural-language secretary response.
    """

    available_minutes = int(
        plan.get(
            "available_minutes",
            0,
        )
    )

    recommendations = plan.get(
        "recommendations",
        [],
    )

    if not recommendations:
        return (
            "I don't have any active tasks to recommend "
            "for your available time."
        )

    lines = [
        (
            f"You have {_format_duration(available_minutes)}. "
            "I'd use it like this:"
        )
    ]

    for index, item in enumerate(
        recommendations,
        start=1,
    ):
        title = str(
            item.get(
                "task_title",
                "Untitled task",
            )
        )

        recommended_minutes = int(
            item.get(
                "recommended_minutes",
                0,
            )
        )

        recommendation_type = str(
            item.get(
                "recommendation",
                "",
            )
        )

        partial = bool(
            item.get(
                "partial",
                False,
            )
        )

        lines.append(
            f"{index}. {title} — "
            f"{_format_duration(recommended_minutes)}"
        )

        if recommendation_type == (
            "work_unknown_duration"
        ):
            lines.append(
                "   Its total duration is unknown, "
                "so treat this as a focused work block."
            )

        elif partial:
            lines.append(
                "   This will make partial progress "
                "on the task."
            )

        else:
            lines.append(
                "   This can be completed within "
                "the allocated time."
            )

    remaining = int(
        plan.get(
            "remaining_budget_minutes",
            0,
        )
    )

    if remaining > 0:
        lines.append(
            f"You would still have "
            f"{_format_duration(remaining)} available."
        )
    else:
        lines.append(
            "That uses all of your available time."
        )

    return "\n".join(lines)


def _create_secretary_time_budget_plan(
    available_minutes: int,
    user_id: str,
    db: Session,
) -> dict:
    """
    Load only the current user's active tasks and
    generate a time-budget plan.
    """

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
        )
        .all()
    )

    return create_time_budget_plan(
        tasks=tasks,
        available_minutes=available_minutes,
    )


# ============================================================================
# Memory retrieval
# ============================================================================


def _search_secretary_memory(
    question: str,
    user_id: str,
    db: Session,
):
    """
    Retrieve structured secretary knowledge using deterministic
    lexical matching.

    pgvector semantic retrieval can be added later after this
    foundation is fully verified.
    """

    words = [
        word.strip(
            ".,?!:;()[]{}\\\"'"
        )
        for word in question.lower().split()
    ]

    words = [
        word
        for word in words
        if len(word) >= 3
        and word not in {
            "what",
            "when",
            "where",
            "which",
            "who",
            "whom",
            "does",
            "did",
            "the",
            "for",
            "from",
            "with",
            "about",
            "need",
            "want",
            "tell",
            "show",
            "give",
            "have",
            "has",
            "had",
            "is",
            "are",
            "was",
            "were",
            "and",
            "should",
            "could",
            "would",
            "can",
            "this",
            "that",
        }
    ]

    # ------------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------------

    entity_query = db.query(
        Entity
    ).filter(
        Entity.user_id == user_id
    )

    if words:

        entity_conditions = [
            Entity.name.ilike(
                f"%{word}%"
            )
            for word in words
        ]

        entity_conditions += [
            Entity.description.ilike(
                f"%{word}%"
            )
            for word in words
        ]

        entities = (
            entity_query
            .filter(
                or_(
                    *entity_conditions
                )
            )
            .order_by(
                Entity.updated_at.desc()
            )
            .limit(20)
            .all()
        )

    else:

        entities = (
            entity_query
            .order_by(
                Entity.updated_at.desc()
            )
            .limit(20)
            .all()
        )

    # If lexical matching found nothing, retrieve recent entities.

    if not entities:

        entities = (
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
        for entity in entities
    }

    # ------------------------------------------------------------------------
    # Facts
    # ------------------------------------------------------------------------

    fact_query = db.query(
        Fact
    ).filter(
        Fact.user_id == user_id
    )

    if entity_ids:

        facts = (
            fact_query
            .filter(
                Fact.entity_id.in_(
                    entity_ids
                )
            )
            .filter(
                Fact.is_current.is_(True)
            )
            .order_by(
                Fact.updated_at.desc()
            )
            .limit(50)
            .all()
        )

    else:

        facts = (
            fact_query
            .filter(
                Fact.is_current.is_(True)
            )
            .order_by(
                Fact.updated_at.desc()
            )
            .limit(50)
            .all()
        )

    # ------------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------------

    relationship_query = db.query(
        EntityRelationship
    ).filter(
        EntityRelationship.user_id == user_id,
        EntityRelationship.is_current.is_(True),
    )

    if entity_ids:

        relationships = (
            relationship_query
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
            .limit(50)
            .all()
        )

    else:

        relationships = (
            relationship_query
            .order_by(
                EntityRelationship.created_at.desc()
            )
            .limit(50)
            .all()
        )

    # ------------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------------

    event_query = db.query(
        Event
    ).filter(
        Event.user_id == user_id
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
            .limit(50)
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

    # ------------------------------------------------------------------------
    # Memories
    # ------------------------------------------------------------------------

    memory_query = db.query(
        Memory
    ).filter(
        Memory.user_id == user_id,
        Memory.is_active.is_(True),
    )

    if entity_ids:

        memories = (
            memory_query
            .filter(
                Memory.entity_id.in_(
                    entity_ids
                )
            )
            .order_by(
                Memory.importance.desc(),
                Memory.updated_at.desc(),
            )
            .limit(50)
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
        entities,
        facts,
        relationships,
        events,
        memories,
    )


# ============================================================================
# Context builder
# ============================================================================


def _build_grounded_context(
    entities,
    facts,
    relationships,
    events,
    memories,
):
    """
    Convert database records into a compact grounded context
    for Gemma.
    """

    entity_names = {
        entity.id: entity.name
        for entity in entities
    }

    lines = []

    # ------------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------------

    lines.append("ENTITIES:")

    for entity in entities:

        description = _safe_text(
            entity.description
        )

        if description:

            lines.append(
                f"- [{entity.entity_type}] "
                f"{entity.name}: {description}"
            )

        else:

            lines.append(
                f"- [{entity.entity_type}] "
                f"{entity.name}"
            )

    lines.append("")

    # ------------------------------------------------------------------------
    # Facts
    # ------------------------------------------------------------------------

    lines.append("FACTS:")

    for fact in facts:

        entity_name = entity_names.get(
            fact.entity_id,
            "Unknown entity",
        )

        value = _fact_value(
            fact
        )

        unit = (
            f" {fact.unit}"
            if fact.unit
            else ""
        )

        lines.append(
            f"- {entity_name} | "
            f"{fact.key} = "
            f"{_safe_text(value)}{unit}"
        )

    lines.append("")

    # ------------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------------

    lines.append("RELATIONSHIPS:")

    for relationship in relationships:

        source = entity_names.get(
            relationship.source_entity_id,
            "Unknown",
        )

        target = entity_names.get(
            relationship.target_entity_id,
            "Unknown",
        )

        lines.append(
            f"- {source} "
            f"--{relationship.relationship_type}--> "
            f"{target}"
        )

    lines.append("")

    # ------------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------------

    lines.append("EVENTS:")

    for event in events:

        primary_entity = entity_names.get(
            event.primary_entity_id,
            "Unknown entity",
        )

        event_time = _safe_text(
            event.event_time
        )

        lines.append(
            f"- [{event.event_type}] "
            f"{event.title} | "
            f"entity={primary_entity} | "
            f"time={event_time}"
        )

        if event.description:

            lines.append(
                f"  description: "
                f"{event.description}"
            )

    lines.append("")

    # ------------------------------------------------------------------------
    # Memories
    # ------------------------------------------------------------------------

    lines.append("MEMORIES:")

    for memory in memories:

        entity_name = entity_names.get(
            memory.entity_id,
            "Unknown entity",
        )

        lines.append(
            f"- [{memory.memory_type}] "
            f"{memory.content} "
            f"(entity={entity_name}, "
            f"importance={memory.importance}, "
            f"confidence={memory.confidence})"
        )

    return "\n".join(lines)


# ============================================================================
# Intent detection
# ============================================================================


def _detect_secretary_intent(
    question: str,
) -> str:
    """
    Detect the primary information type requested by the user.
    """

    # Time-budget detection comes first because questions such as
    # "I have 20 minutes, what should I do?" could otherwise
    # accidentally be treated as a generic question.

    if _is_time_budget_question(
        question
    ):
        return "time_budget"

    q = question.lower().strip()

    # Deadline / due-date questions

    if any(
        phrase in q
        for phrase in (
            "deadline",
            "due date",
            "due by",
            "when is it due",
            "when does it need to be finished",
            "when does it need to be done",
            "when should it be finished",
            "by when",
        )
    ):
        return "deadline"

    # Review / follow-up questions

    if any(
        phrase in q
        for phrase in (
            "review",
            "follow up",
            "follow-up",
            "followup",
            "check back",
            "check on",
        )
    ):
        return "review"

    # Responsibility questions

    if any(
        phrase in q
        for phrase in (
            "who is responsible",
            "who handles",
            "who is handling",
            "who was assigned",
            "assigned to whom",
            "who owns",
            "who has the task",
        )
    ):
        return "responsibility"

    # Budget / cost / amount questions

    if any(
        phrase in q
        for phrase in (
            "budget",
            "cost",
            "price",
            "amount",
            "how much",
            "money",
        )
    ):
        return "budget"

    # Task/work questions

    if any(
        phrase in q
        for phrase in (
            "what task",
            "what tasks",
            "what work",
            "what project",
            "what did i give",
            "what was assigned",
            "what do i need to do",
        )
    ):
        return "task"

    return "general"


# ============================================================================
# Deterministic answers for authoritative structured memory
# ============================================================================


def _extract_deadline_text(
    event: Event,
) -> Optional[str]:
    """
    Extract a human-readable deadline from a stored event.
    """

    title = _safe_text(
        event.title
    ).strip()

    description = _safe_text(
        event.description
    ).strip()

    # Example:
    # "ABC website project deadline: Friday"

    if ":" in title:

        candidate = title.rsplit(
            ":",
            1,
        )[1].strip()

        if candidate:
            return candidate

    # Example:
    # "Deadline is Friday."

    match = re.search(
        r"deadline\s+(?:is|was|for)\s+(.+)",
        description,
        flags=re.IGNORECASE,
    )

    if match:

        return (
            match.group(1)
            .strip()
            .rstrip(".")
        )

    # Fallback to event_time if available.

    if event.event_time:

        return _safe_text(
            event.event_time
        )

    return None


def _extract_review_text(
    event: Event,
) -> Optional[str]:
    """
    Extract a human-readable review/follow-up time.
    """

    title = _safe_text(
        event.title
    ).strip()

    description = _safe_text(
        event.description
    ).strip()

    # Example:
    # "Review ABC website project after 3 days"

    match = re.search(
        r"(after\s+.+)$",
        title,
        flags=re.IGNORECASE,
    )

    if match:

        return (
            match.group(1)
            .strip()
            .rstrip(".")
        )

    # Example:
    # "Review requested after 3 days."

    match = re.search(
        r"(after\s+.+)$",
        description,
        flags=re.IGNORECASE,
    )

    if match:

        return (
            match.group(1)
            .strip()
            .rstrip(".")
        )

    if event.event_time:

        return _safe_text(
            event.event_time
        )

    return None


def _deterministic_secretary_answer(
    intent: str,
    entities,
    facts,
    relationships,
    events,
    memories,
) -> Optional[str]:
    """
    Answer authoritative secretary questions directly from
    structured database records.
    """

    # ------------------------------------------------------------------------
    # DEADLINE
    # ------------------------------------------------------------------------

    if intent == "deadline":

        deadline_events = [
            event
            for event in events
            if str(
                event.event_type
            ).upper() == "DEADLINE"
        ]

        if deadline_events:

            for event in deadline_events:

                deadline_text = (
                    _extract_deadline_text(
                        event
                    )
                )

                if deadline_text:

                    return (
                        f"The deadline is "
                        f"{deadline_text}."
                    )

            event = deadline_events[0]

            if event.event_time:

                return (
                    "The deadline is "
                    f"{_safe_text(event.event_time)}."
                )

        return None

    # ------------------------------------------------------------------------
    # REVIEW / FOLLOW-UP
    # ------------------------------------------------------------------------

    if intent == "review":

        # Map entity IDs to their names.
        #
        # Example:
        #
        # event.primary_entity_id = 8
        # entity 8 = "ABC website project"
        #
        # This allows the answer to identify the actual
        # project instead of incorrectly referring to a person.

        entity_names = {
            entity.id: _safe_text(
                entity.name
            ).strip()
            for entity in entities
            if entity.name
        }

        review_events = [
            event
            for event in events
            if str(
                event.event_type
            ).upper()
            in {
                "REVIEW",
                "FOLLOW_UP",
            }
        ]

        if review_events:

            for event in review_events:

                review_text = (
                    _extract_review_text(
                        event
                    )
                )

                # ------------------------------------------------------------
                # Resolve the entity attached to this review event.
                #
                # The current database contains:
                #
                # REVIEW
                # "Review ABC website project after 3 days"
                #
                # primary_entity_id = 8
                #
                # Entity 8 = ABC website project
                # ------------------------------------------------------------

                primary_entity_name = (
                    entity_names.get(
                        event.primary_entity_id
                    )
                )

                if primary_entity_name:

                    if review_text:

                        return (
                            f"You should review "
                            f"{primary_entity_name} "
                            f"{review_text}."
                        )

                    if event.event_time:

                        return (
                            f"You should review "
                            f"{primary_entity_name} "
                            f"on "
                            f"{_safe_text(event.event_time)}."
                        )

                    return (
                        f"You should review "
                        f"{primary_entity_name}."
                    )

                # ------------------------------------------------------------
                # Fallback when no primary entity is attached.
                # ------------------------------------------------------------

                if review_text:

                    return (
                        "You should review it "
                        f"{review_text}."
                    )

            # ------------------------------------------------------------
            # Last event-level fallback.
            # ------------------------------------------------------------

            event = review_events[0]

            if event.event_time:

                return (
                    "The review is scheduled for "
                    f"{_safe_text(event.event_time)}."
                )

        # ------------------------------------------------------------
        # Memory fallback.
        # ------------------------------------------------------------

        for memory in memories:

            memory_type = str(
                memory.memory_type or ""
            ).lower()

            content = _safe_text(
                memory.content
            ).strip()

            if (
                memory_type
                in {
                    "follow_up",
                    "review",
                }
                and content
            ):

                return content

        return None

    # ------------------------------------------------------------------------
    # RESPONSIBILITY
    # ------------------------------------------------------------------------

    if intent == "responsibility":

        responsibility_relationships = [
            relationship
            for relationship in relationships
            if str(
                relationship.relationship_type
            ).lower()
            in {
                "responsible_for",
                "assigned_to",
                "owns",
            }
        ]

        if responsibility_relationships:

            entity_names = {
                entity.id: entity.name
                for entity in entities
            }

            relationship = (
                responsibility_relationships[0]
            )

            person = entity_names.get(
                relationship.source_entity_id
            )

            project = entity_names.get(
                relationship.target_entity_id
            )

            if person and project:

                return (
                    f"{person} is responsible "
                    f"for {project}."
                )

            if person:

                return (
                    f"{person} is responsible "
                    "for it."
                )

        # Memory fallback.

        for memory in memories:

            memory_type = str(
                memory.memory_type or ""
            ).lower()

            content = _safe_text(
                memory.content
            ).strip()

            if (
                memory_type
                == "responsibility"
                and content
            ):

                return content

        return None

    # ------------------------------------------------------------------------
    # BUDGET
    # ------------------------------------------------------------------------

    if intent == "budget":

        numeric_facts = [
            fact
            for fact in facts
            if str(
                fact.value_type or ""
            ).lower() == "number"
            and fact.value_number is not None
        ]

        budget_facts = [
            fact
            for fact in numeric_facts
            if "budget"
            in str(
                fact.key or ""
            ).lower()
        ]

        selected_facts = (
            budget_facts
            if budget_facts
            else numeric_facts
        )

        if selected_facts:

            fact = selected_facts[0]

            value = fact.value_number

            if (
                isinstance(value, float)
                and value.is_integer()
            ):

                value_text = str(
                    int(value)
                )

            else:

                value_text = str(
                    value
                )

            if fact.unit:

                return (
                    f"{value_text} "
                    f"{fact.unit}"
                )

            return value_text

        return None

    # ------------------------------------------------------------------------
    # TASK
    # ------------------------------------------------------------------------

    if intent == "task":

        task_entities = [
            entity
            for entity in entities
            if str(
                entity.entity_type or ""
            ).upper() == "TASK"
        ]

        if task_entities:

            task_names = [
                entity.name.strip()
                for entity in task_entities
                if entity.name
            ]

            if task_names:

                if len(task_names) == 1:

                    return (
                        f"The task is "
                        f"{task_names[0]}."
                    )

                return (
                    "The tasks are "
                    + ", ".join(task_names)
                    + "."
                )

        # Memory fallback.

        task_memories = [
            memory
            for memory in memories
            if str(
                memory.memory_type or ""
            ).lower()
            in {
                "task",
                "task_context",
            }
            and _safe_text(
                memory.content
            ).strip()
        ]

        if task_memories:

            contents = [
                _safe_text(
                    memory.content
                ).strip()
                for memory in task_memories
            ]

            if len(contents) == 1:

                return (
                    f"The task is "
                    f"{contents[0]}."
                )

            return (
                "The tasks are "
                + ", ".join(contents)
                + "."
            )

        return None

    return None


# ============================================================================
# Gemma answer generation
# ============================================================================


def _run_secretary_answer(
    question: str,
    context: str,
) -> str:
    """
    Generate a grounded natural-language answer using local Gemma.

    The database context is authoritative.
    """

    llama_cli_path = os.getenv(
        "LLAMA_CLI_PATH",
        r"D:\Management_model\llama.cpp\build\bin\Release\llama-cli.exe",
    )

    gemma_model_path = os.getenv(
        "GEMMA_MODEL_PATH",
        r"D:\Management_model\models\gemma-3-1b-it-q4_0.gguf",
    )

    timeout = int(
        os.getenv(
            "LLAMA_TIMEOUT",
            "120",
        )
    )

    context_size = int(
        os.getenv(
            "LLAMA_CONTEXT",
            "2048",
        )
    )

    max_tokens = int(
        os.getenv(
            "LLAMA_MAX_TOKENS",
            "128",
        )
    )

    prompt = f"""
You are a personal secretary.

Answer the user's question using ONLY the supplied secretary memory.

SECRETARY MEMORY:

{context}

USER QUESTION:

{question}

Rules:

1. Answer the question directly and naturally.
2. Use ONLY information explicitly present in SECRETARY MEMORY.
3. Never invent names, dates, amounts, tasks, responsibilities, or relationships.
4. If the answer is present in the memory, give it.
5. If the answer is not present, say exactly:

I don't have that information in my memory.

6. Keep the answer short.
7. Return ONLY the final answer.
8. Do not return JSON.
9. Do not return analysis or reasoning.
10. Do not repeat the question.

ANSWER:
""".strip()

    output_file = tempfile.NamedTemporaryFile(
        prefix="secretary_answer_",
        suffix=".txt",
        delete=False,
    ).name

    try:

        command = [
            llama_cli_path,
            "-m",
            gemma_model_path,
            "-p",
            prompt,
            "-n",
            str(max_tokens),
            "-c",
            str(context_size),
            "-st",
            "--no-conversation",
            "--single-turn",
            "--no-display-prompt",
            "--simple-io",
            "--no-show-timings",
            "--color",
            "off",
            "--log-colors",
            "off",
            "--output-file",
            output_file,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

        stderr = (
            result.stderr or b""
        ).decode(
            "utf-8",
            errors="replace",
        ).strip()

        if result.returncode != 0:

            raise RuntimeError(
                "Gemma failed to generate an answer. "
                f"Exit code: {result.returncode}. "
                f"{stderr[-1000:]}"
            )

        try:

            with open(
                output_file,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:

                answer = file.read()

        except OSError as exc:

            raise RuntimeError(
                "Could not read Gemma output file: "
                f"{output_file}"
            ) from exc

        # --------------------------------------------------------------------
        # Clean ANSI/control characters
        # --------------------------------------------------------------------

        answer = re.sub(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])",
            "",
            answer,
        )

        answer = "".join(
            character
            for character in answer
            if character in "\n\r\t"
            or ord(character) >= 32
        )

        answer = answer.strip()

        # --------------------------------------------------------------------
        # Remove prompt labels
        # --------------------------------------------------------------------

        if "ANSWER:" in answer:

            answer = answer.split(
                "ANSWER:",
                1,
            )[-1].strip()

        for prefix in (
            "Assistant:",
            "assistant:",
            "ASSISTANT:",
            "Assistant",
            "assistant",
        ):

            if answer.startswith(prefix):

                answer = answer[
                    len(prefix):
                ].strip()

        # --------------------------------------------------------------------
        # Remove llama.cpp informational lines
        # --------------------------------------------------------------------

        lines = []

        for line in answer.splitlines():

            stripped = line.strip()

            if not stripped:
                continue

            lower = stripped.lower()

            if (
                lower.startswith("build")
                or lower.startswith("model")
                or lower.startswith("system info")
                or lower.startswith("system prompt")
                or lower.startswith("llama_")
                or lower.startswith("sampling")
                or lower.startswith("generation")
                or lower.startswith("load time")
                or lower.startswith("prompt eval")
                or lower.startswith("eval time")
                or lower.startswith("total time")
                or lower.startswith("tokens")
            ):
                continue

            lines.append(
                stripped
            )

        answer = "\n".join(
            lines
        ).strip()

        # --------------------------------------------------------------------
        # Fix common UTF-8/console mojibake
        # --------------------------------------------------------------------

        answer = (
            answer
            .replace(
                "donâ€™t",
                "don't",
            )
            .replace(
                "doesnâ€™t",
                "doesn't",
            )
            .replace(
                "isnâ€™t",
                "isn't",
            )
            .replace(
                "canâ€™t",
                "can't",
            )
            .replace(
                "â€“",
                "-",
            )
            .replace(
                "â€”",
                "-",
            )
        )

        # --------------------------------------------------------------------
        # Final safety check
        # --------------------------------------------------------------------

        if not answer:

            raise RuntimeError(
                "Gemma returned no usable "
                "secretary answer."
            )

        garbage_markers = (
            "build      :",
            "model      :",
            "ftype      :",
            "modalities :",
        )

        if any(
            marker in answer
            for marker in garbage_markers
        ):

            raise RuntimeError(
                "Gemma output contained unusable "
                "terminal output: "
                + repr(
                    answer[:500]
                )
            )

        return answer

    except subprocess.TimeoutExpired as exc:

        raise RuntimeError(
            f"Gemma timed out after "
            f"{timeout} seconds."
        ) from exc

    except FileNotFoundError as exc:

        raise RuntimeError(
            "llama-cli executable was not found: "
            f"{llama_cli_path}"
        ) from exc

    finally:

        try:

            if os.path.exists(
                output_file
            ):

                os.remove(
                    output_file
                )

        except OSError:
            pass


# ============================================================================
# Ask secretary
# ============================================================================


@router.post("/ask")
def ask_secretary(
    request: SecretaryAskRequest,
    db: Session = Depends(get_db),
):
    """
    Ask a natural-language question against stored secretary memory.

    Supports:
    - deadline questions
    - review questions
    - responsibility questions
    - budget questions
    - task questions
    - time-budget planning
    - general Gemma-powered questions
    """

    question = request.question.strip()

    if not question:

        return {
            "answer": "Please provide a question.",
            "sources": {},
        }

    # ========================================================================
    # TIME-BUDGET PLANNING
    # ========================================================================

    if _is_time_budget_question(
        question
    ):

        available_minutes = (
            _parse_time_budget(
                question
            )
        )

        if (
            available_minutes is not None
            and available_minutes > 0
        ):

            plan = (
                _create_secretary_time_budget_plan(
                    available_minutes=available_minutes,
                    user_id=request.user_id,
                    db=db,
                )
            )

            answer = _build_time_budget_answer(
                plan
            )

            return {
                "answer": answer,

                "sources": {
                    "intent": "time_budget",
                    "answer_source": (
                        "time_budget_planner"
                    ),
                    "user_id": request.user_id,
                    "available_minutes": (
                        available_minutes
                    ),
                    "tasks_considered": (
                        plan.get(
                            "tasks_considered",
                            0,
                        )
                    ),
                    "recommendations": len(
                        plan.get(
                            "recommendations",
                            [],
                        )
                    ),
                },

                "plan": plan,
            }

    # ========================================================================
    # Retrieve memory
    # ========================================================================

    (
        entities,
        facts,
        relationships,
        events,
        memories,
    ) = _search_secretary_memory(
        question=question,
        user_id=request.user_id,
        db=db,
    )

    # ========================================================================
    # Detect question type
    # ========================================================================

    intent = _detect_secretary_intent(
        question
    )

    # ========================================================================
    # Try deterministic answer first
    # ========================================================================

    deterministic_answer = (
        _deterministic_secretary_answer(
            intent=intent,
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
                "intent": intent,
                "answer_source": (
                    "structured_memory"
                ),
            },
        }

    # ========================================================================
    # Build grounded context for Gemma
    # ========================================================================

    context = _build_grounded_context(
        entities=entities,
        facts=facts,
        relationships=relationships,
        events=events,
        memories=memories,
    )

    # ========================================================================
    # General question -> Gemma
    # ========================================================================

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
            "intent": intent,
            "answer_source": "gemma",
        },
    }