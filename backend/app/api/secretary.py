from datetime import date, datetime
from typing import Optional
import json
import os
import re
import subprocess
import tempfile

from fastapi import APIRouter, Depends, Query, HTTPException
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
    Embedding,
)

from ..models.task import Task

from ..services.embedding_service import (
    generate_embedding,
    EMBEDDING_MODEL_NAME,
)

from ..services.time_budget_planner import (
    create_time_budget_plan,
)

from ..services.nlp_understanding import (
    understand_question,
)

from ..services.schedule_retrieval import (
    get_schedule_for_date,
)


try:
    from nltk.corpus import stopwords

    ENGLISH_STOPWORDS = set(
        stopwords.words("english")
    )

except Exception:
    ENGLISH_STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "here",
        "hers",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "she",
        "should",
        "that",
        "the",
        "their",
        "them",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }


SECRETARY_SEARCH_STOPWORDS = {
    "tell",
    "show",
    "give",
    "need",
    "want",
    "know",
    "please",
    "find",
    "get",
    "remember",
    "remembering",
    "thing",
    "things",
}


router = APIRouter(
    prefix="/ai/secretary",
    tags=["AI Secretary"],
)


@router.get("/notes")
def list_notes(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    user_id: str = "default",
    db: Session = Depends(get_db),
):
    notes = (
        db.query(RawNote)
        .filter(
            RawNote.user_id == user_id
        )
        .order_by(
            RawNote.created_at.desc()
        )
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


@router.get(
    "/conversations/{conversation_id}/messages"
)
def conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
):
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
    entities = (
        db.query(Entity)
        .filter(
            Entity.user_id == user_id
        )
        .order_by(
            Entity.created_at.asc()
        )
        .all()
    )

    entity_by_id = {
        entity.id: entity.name
        for entity in entities
    }

    facts = (
        db.query(Fact)
        .filter(
            Fact.user_id == user_id
        )
        .order_by(
            Fact.created_at.asc()
        )
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
        .filter(
            Event.user_id == user_id
        )
        .order_by(
            Event.created_at.asc()
        )
        .all()
    )

    memories = (
        db.query(Memory)
        .filter(
            Memory.user_id == user_id,
            Memory.is_active.is_(True),
        )
        .order_by(
            Memory.created_at.asc()
        )
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
                "source_note_id": relationship.source_note_id,
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
                "source_note_id": event.source_note_id,
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
                "source_note_id": memory.source_note_id,
            }
            for memory in memories
        ],
    }


class SecretaryAskRequest(BaseModel):
    question: str
    user_id: str = "default"


def _fact_value(fact: Fact):
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
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _count_entities(
    db: Session,
    user_id: str,
) -> int:
    return (
        db.query(Entity)
        .filter(
            Entity.user_id == user_id
        )
        .count()
    )


def _count_facts(
    db: Session,
    user_id: str,
) -> int:
    return (
        db.query(Fact)
        .filter(
            Fact.user_id == user_id
        )
        .count()
    )


def _count_relationships(
    db: Session,
    user_id: str,
) -> int:
    return (
        db.query(EntityRelationship)
        .filter(
            EntityRelationship.user_id == user_id
        )
        .count()
    )


def _count_events(
    db: Session,
    user_id: str,
) -> int:
    return (
        db.query(Event)
        .filter(
            Event.user_id == user_id
        )
        .count()
    )


def _count_memories(
    db: Session,
    user_id: str,
) -> int:
    return (
        db.query(Memory)
        .filter(
            Memory.user_id == user_id
        )
        .count()
    )


def _extract_search_terms(
    question: str,
) -> list[str]:
    text = question.lower()

    tokens = re.findall(
        r"[a-zA-Z0-9]+",
        text,
    )

    terms = []

    for token in tokens:
        if len(token) < 2:
            continue

        if token in ENGLISH_STOPWORDS:
            continue

        if token in SECRETARY_SEARCH_STOPWORDS:
            continue

        terms.append(token)

    return list(
        dict.fromkeys(terms)
    )


def _parse_time_budget(
    question: str,
) -> Optional[int]:
    if not question:
        return None

    q = question.lower().strip()

    if re.search(
        r"\bhalf\s+an?\s+hour\b",
        q,
    ):
        return 30

    if re.search(
        r"\bquarter\s+of\s+an?\s+hour\b",
        q,
    ):
        return 15

    if re.search(
        r"\ban?\s+hour\b",
        q,
    ):
        if not re.search(
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:hours?|hrs?)\b",
            q,
        ):
            return 60

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:hours?|hrs?)"
        r"\s*(?:and\s*)?"
        r"(\d+(?:\.\d+)?)\s*"
        r"(?:minutes?|mins?)\b",
        q,
    )

    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2))

        return round(
            hours * 60 + minutes
        )

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:hours?|hrs?)\b",
        q,
    )

    if match:
        return round(
            float(match.group(1)) * 60
        )

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:minutes?|mins?)\b",
        q,
    )

    if match:
        return round(
            float(match.group(1))
        )

    return None


def _is_time_budget_question(
    question: str,
) -> bool:
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


def _build_time_budget_answer(
    plan: dict,
) -> str:
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
            "I don't have any active tasks "
            "to recommend for your available time."
        )

    lines = [
        (
            f"You have "
            f"{_format_duration(available_minutes)}. "
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
        ).strip()

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
        ).strip()

        partial = bool(
            item.get(
                "partial",
                False,
            )
        )

        lines.append(
            f"{index}. {title} - "
            f"{_format_duration(recommended_minutes)}"
        )

        if recommendation_type == (
            "work_unknown_duration"
        ):
            lines.append(
                "   Its total duration is unknown, "
                "so use this as a focused work block."
            )

        elif partial:
            lines.append(
                "   This will make partial progress "
                "on the task."
            )

        else:
            lines.append(
                "   This should complete the task."
            )

    total_recommended_minutes = int(
        plan.get(
            "total_recommended_minutes",
            0,
        )
    )

    remaining_budget_minutes = int(
        plan.get(
            "remaining_budget_minutes",
            0,
        )
    )

    if remaining_budget_minutes <= 0:
        lines.append(
            "That uses all of your available time."
        )

    elif total_recommended_minutes > 0:
        lines.append(
            "You would still have "
            f"{_format_duration(remaining_budget_minutes)} "
            "available."
        )

    return "\n".join(lines)


def _semantic_memory_search(
    question: str,
    user_id: str,
    db: Session,
    limit: int = 20,
):
    try:
        query_vector = generate_embedding(
            question
        )

        if not query_vector:
            return []

        semantic_results = (
            db.query(
                Memory,
                Embedding.embedding.cosine_distance(
                    query_vector
                ).label("distance"),
            )
            .join(
                Embedding,
                Embedding.memory_id == Memory.id,
            )
            .filter(
                Memory.user_id == user_id,
                Memory.is_active.is_(True),
                Embedding.model_name
                == EMBEDDING_MODEL_NAME,
            )
            .order_by(
                Embedding.embedding.cosine_distance(
                    query_vector
                ).asc()
            )
            .limit(limit)
            .all()
        )

        return [
            memory
            for memory, _distance
            in semantic_results
        ]

    except Exception:
        return []


def _search_secretary_memory(
    question: str,
    user_id: str,
    db: Session,
):
    semantic_memories = _semantic_memory_search(
        question=question,
        user_id=user_id,
        db=db,
        limit=20,
    )

    words = _extract_search_terms(
        question
    )

    entity_query = (
        db.query(Entity)
        .filter(
            Entity.user_id == user_id
        )
    )

    lexical_entities = []

    if words:
        entity_conditions = []

        for word in words:
            entity_conditions.append(
                Entity.name.ilike(
                    f"%{word}%"
                )
            )

            entity_conditions.append(
                Entity.description.ilike(
                    f"%{word}%"
                )
            )

        lexical_entities = (
            entity_query
            .filter(
                or_(*entity_conditions)
            )
            .order_by(
                Entity.updated_at.desc()
            )
            .limit(20)
            .all()
        )

    entity_ids = {
        memory.entity_id
        for memory in semantic_memories
        if memory.entity_id is not None
    }

    entity_ids.update(
        entity.id
        for entity in lexical_entities
    )

    if entity_ids:
        related_relationships = (
            db.query(EntityRelationship)
            .filter(
                EntityRelationship.user_id
                == user_id,
                EntityRelationship.is_current.is_(
                    True
                ),
                or_(
                    EntityRelationship.source_entity_id.in_(
                        entity_ids
                    ),
                    EntityRelationship.target_entity_id.in_(
                        entity_ids
                    ),
                ),
            )
            .limit(50)
            .all()
        )

        for relationship in related_relationships:
            entity_ids.add(
                relationship.source_entity_id
            )
            entity_ids.add(
                relationship.target_entity_id
            )

    if entity_ids:
        entities = (
            db.query(Entity)
            .filter(
                Entity.user_id == user_id,
                Entity.id.in_(entity_ids),
            )
            .order_by(
                Entity.updated_at.desc()
            )
            .limit(30)
            .all()
        )

    else:
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

    fact_query = (
        db.query(Fact)
        .filter(
            Fact.user_id == user_id
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

    relationship_query = (
        db.query(EntityRelationship)
        .filter(
            EntityRelationship.user_id == user_id,
            EntityRelationship.is_current.is_(True),
        )
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

    memory_map = {
        memory.id: memory
        for memory in semantic_memories
    }

    if entity_ids:
        related_memories = (
            db.query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.is_active.is_(True),
                Memory.entity_id.in_(
                    entity_ids
                ),
            )
            .order_by(
                Memory.importance.desc(),
                Memory.updated_at.desc(),
            )
            .limit(50)
            .all()
        )

        for memory in related_memories:
            memory_map[memory.id] = memory

    memories = list(
        memory_map.values()
    )

    semantic_ids = {
        memory.id
        for memory in semantic_memories
    }

    memories.sort(
        key=lambda memory: (
            0
            if memory.id in semantic_ids
            else 1,
            -float(
                memory.importance or 0
            ),
            memory.updated_at
            or datetime.min,
        )
    )

    memories = memories[:50]

    return (
        entities,
        facts,
        relationships,
        events,
        memories,
    )


def _build_grounded_context(
    entities,
    facts,
    relationships,
    events,
    memories,
):
    entity_names = {
        entity.id: entity.name
        for entity in entities
    }

    lines = ["ENTITIES:"]

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
    lines.append("FACTS:")

    for fact in facts:
        entity_name = entity_names.get(
            fact.entity_id,
            "Unknown entity",
        )

        value = _fact_value(fact)

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


def _build_secretary_context(
    db: Session,
    user_id: str,
    question: str,
) -> str:
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

    return _build_grounded_context(
        entities=entities,
        facts=facts,
        relationships=relationships,
        events=events,
        memories=memories,
    )


def _detect_secretary_intent(
    question: str,
) -> str:
    if _is_time_budget_question(
        question
    ):
        return "time_budget"

    q = question.lower().strip()

    if any(
        phrase in q
        for phrase in (
            "when is the deadline",
            "what is the deadline",
            "what's the deadline",
            "deadline for",
            "deadline of",
            "when is it due",
            "when is this due",
            "when does it need to be done",
            "when should it be completed",
            "by when",
            "due date",
            "due by",
        )
    ):
        return "deadline"

    if any(
        phrase in q
        for phrase in (
            "when should i review",
            "when do i review",
            "when to review",
            "when should we review",
            "when do we review",
            "review after",
            "review in",
            "when is the review",
            "when should the review",
            "when is review",
        )
    ):
        return "review"

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
            "what responsibility",
            "what responsibilities",
            "responsibilities did i give",
            "what did i assign",
            "what did i give",
            "what was given to",
            "what responsibilities does",
            "what is responsible for",
        )
    ):
        return "responsibility"

    if any(
        phrase in q
        for phrase in (
            "how much money",
            "how much is allocated",
            "how much budget",
            "what is the budget",
            "what's the budget",
            "budget for",
            "budget of",
            "allocated amount",
            "allocated money",
            "project cost",
            "how much will",
            "how much does it cost",
        )
    ):
        return "budget"

    if any(
        phrase in q
        for phrase in (
            "what task",
            "what tasks",
            "what work",
            "what website work",
            "what work is",
            "what work does",
            "what work are",
            "what is handling",
            "what is he handling",
            "what is she handling",
            "what is arun handling",
            "what is assigned",
            "what is he assigned",
            "what is she assigned",
            "what tasks is",
            "what tasks are",
            "what is working on",
            "what is he working on",
            "what is she working on",
            "what is arun working on",
            "what project",
            "what did i give",
            "what was assigned",
            "what do i need to do",
            "what do we need to do",
            "what needs to be done",
        )
    ):
        return "task"

    return "general"


def _extract_deadline_text(
    event: Event,
) -> Optional[str]:
    title = _safe_text(
        event.title
    ).strip()

    description = _safe_text(
        event.description
    ).strip()

    if ":" in title:
        candidate = title.rsplit(
            ":",
            1,
        )[1].strip()

        if candidate:
            return candidate

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

    if event.event_time:
        return _safe_text(
            event.event_time
        )

    return None


def _normalize_review_text(
    value: str,
) -> str:
    value = (
        value
        .strip()
        .rstrip(".")
    )

    value = re.sub(
        r"(?i)\bafter(?=\d)",
        "after ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _extract_review_text(
    event: Event,
) -> Optional[str]:
    title = _safe_text(
        event.title
    ).strip()

    description = _safe_text(
        event.description
    ).strip()

    match = re.search(
        r"(after\s+.+)$",
        title,
        flags=re.IGNORECASE,
    )

    if match:
        return _normalize_review_text(
            match.group(1)
        )

    match = re.search(
        r"(after\s+.+)$",
        description,
        flags=re.IGNORECASE,
    )

    if match:
        return _normalize_review_text(
            match.group(1)
        )

    if event.event_time:
        return _safe_text(
            event.event_time
        )

    return None


def _deterministic_secretary_answer(
    question: str,
    intent: str,
    entities,
    facts,
    relationships,
    events,
    memories,
) -> Optional[str]:
    question_lower = (
        _safe_text(question)
        .lower()
        .strip()
    )

    entity_names = {
        entity.id: _safe_text(
            entity.name
        ).strip()
        for entity in entities
        if entity.name
    }

    entity_types = {
        entity.id: str(
            entity.entity_type or ""
        ).upper()
        for entity in entities
    }

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
                        "The deadline is "
                        f"{deadline_text}."
                    )

            event = deadline_events[0]

            if event.event_time:
                return (
                    "The deadline is "
                    f"{_safe_text(event.event_time)}."
                )

        return None

    if intent == "review":
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

        mentioned_review_events = [
            event
            for event in review_events
            if (
                entity_names.get(
                    event.primary_entity_id
                )
                and entity_names.get(
                    event.primary_entity_id
                ).lower()
                in question_lower
            )
        ]

        if mentioned_review_events:
            review_events = (
                mentioned_review_events
            )

        if review_events:
            for event in review_events:
                review_text = (
                    _extract_review_text(
                        event
                    )
                )

                primary_entity_name = (
                    entity_names.get(
                        event.primary_entity_id
                    )
                )

                if primary_entity_name:
                    if review_text:
                        return (
                            "You should review "
                            f"{primary_entity_name} "
                            f"{review_text}."
                        )

                    if event.event_time:
                        return (
                            "You should review "
                            f"{primary_entity_name} "
                            "on "
                            f"{_safe_text(event.event_time)}."
                        )

                    return (
                        "You should review "
                        f"{primary_entity_name}."
                    )

                if review_text:
                    return (
                        "You should review it "
                        f"{review_text}."
                    )

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

        mentioned_entities = []

        for entity in entities:
            name = _safe_text(
                entity.name
            ).strip()

            if not name:
                continue

            if name.lower() in question_lower:
                mentioned_entities.append(
                    entity
                )

        mentioned_projects = [
            entity
            for entity in mentioned_entities
            if entity_types.get(entity.id)
            in {
                "PROJECT",
                "TASK",
            }
        ]

        if mentioned_projects:
            for project in mentioned_projects:
                matching_relationships = [
                    relationship
                    for relationship
                    in responsibility_relationships
                    if (
                        relationship.target_entity_id
                        == project.id
                    )
                ]

                if matching_relationships:
                    people = []

                    for relationship in (
                        matching_relationships
                    ):
                        person = entity_names.get(
                            relationship.source_entity_id
                        )

                        if (
                            person
                            and person not in people
                        ):
                            people.append(
                                person
                            )

                    if people:
                        if len(people) == 1:
                            return (
                                f"{people[0]} is responsible "
                                f"for {entity_names[project.id]}."
                            )

                        return (
                            f"{', '.join(people)} are responsible "
                            f"for {entity_names[project.id]}."
                        )

        mentioned_people = [
            entity
            for entity in mentioned_entities
            if entity_types.get(entity.id)
            in {
                "PERSON",
                "USER",
            }
        ]

        if mentioned_people:
            person_ids = {
                entity.id
                for entity in mentioned_people
            }

            assigned_projects = []

            for relationship in (
                responsibility_relationships
            ):
                if (
                    relationship.source_entity_id
                    not in person_ids
                ):
                    continue

                project = entity_names.get(
                    relationship.target_entity_id
                )

                if (
                    project
                    and project not in assigned_projects
                ):
                    assigned_projects.append(
                        project
                    )

            if assigned_projects:
                person_name = _safe_text(
                    mentioned_people[0].name
                ).strip()

                if len(assigned_projects) == 1:
                    return (
                        f"{person_name} is responsible "
                        f"for {assigned_projects[0]}."
                    )

                return (
                    f"{person_name} is responsible for "
                    + ", ".join(
                        assigned_projects
                    )
                    + "."
                )

        if responsibility_relationships:
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

        for memory in memories:
            memory_type = str(
                memory.memory_type or ""
            ).lower()

            content = _safe_text(
                memory.content
            ).strip()

            if (
                memory_type == "responsibility"
                and content
            ):
                return content

        return None

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

        mentioned_entity_ids = {
            entity.id
            for entity in entities
            if entity.name
            and _safe_text(
                entity.name
            ).lower()
            in question_lower
        }

        if mentioned_entity_ids:
            related_budget_facts = [
                fact
                for fact in budget_facts
                if getattr(
                    fact,
                    "entity_id",
                    None,
                )
                in mentioned_entity_ids
            ]

            if related_budget_facts:
                budget_facts = (
                    related_budget_facts
                )

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
                value_text = str(value)

            if fact.unit:
                return (
                    f"{value_text} "
                    f"{fact.unit}"
                )

            return value_text

        return None

    if intent == "task":
        mentioned_entities = []

        for entity in entities:
            name = _safe_text(
                entity.name
            ).strip()

            if not name:
                continue

            if name.lower() in question_lower:
                mentioned_entities.append(
                    entity
                )

        mentioned_people = [
            entity
            for entity in mentioned_entities
            if entity_types.get(entity.id)
            in {
                "PERSON",
                "USER",
            }
        ]

        if mentioned_people:
            person_ids = {
                entity.id
                for entity in mentioned_people
            }

            project_ids = set()

            for relationship in relationships:
                relationship_type = str(
                    relationship.relationship_type
                ).lower()

                if relationship_type not in {
                    "responsible_for",
                    "assigned_to",
                    "owns",
                }:
                    continue

                if (
                    relationship.source_entity_id
                    in person_ids
                ):
                    project_ids.add(
                        relationship.target_entity_id
                    )

            task_ids = set()

            for relationship in relationships:
                relationship_type = str(
                    relationship.relationship_type
                ).lower()

                if relationship_type not in {
                    "contains_task",
                    "contains",
                    "has_task",
                }:
                    continue

                if (
                    relationship.source_entity_id
                    in project_ids
                ):
                    task_ids.add(
                        relationship.target_entity_id
                    )

            task_names = []

            for task_id in task_ids:
                task_name = entity_names.get(
                    task_id
                )

                if (
                    task_name
                    and task_name not in task_names
                ):
                    task_names.append(
                        task_name
                    )

            if task_names:
                if len(task_names) == 1:
                    return (
                        "The task is "
                        f"{task_names[0]}."
                    )

                return (
                    "The tasks are "
                    + ", ".join(task_names)
                    + "."
                )

        mentioned_projects = [
            entity
            for entity in mentioned_entities
            if entity_types.get(entity.id)
            == "PROJECT"
        ]

        if mentioned_projects:
            project_ids = {
                entity.id
                for entity in mentioned_projects
            }

            task_names = []

            for relationship in relationships:
                relationship_type = str(
                    relationship.relationship_type
                ).lower()

                if relationship_type not in {
                    "contains_task",
                    "contains",
                    "has_task",
                }:
                    continue

                if (
                    relationship.source_entity_id
                    not in project_ids
                ):
                    continue

                task_name = entity_names.get(
                    relationship.target_entity_id
                )

                if (
                    task_name
                    and task_name not in task_names
                ):
                    task_names.append(
                        task_name
                    )

            if task_names:
                if len(task_names) == 1:
                    return (
                        "The task is "
                        f"{task_names[0]}."
                    )

                return (
                    "The tasks are "
                    + ", ".join(task_names)
                    + "."
                )

        task_entities = [
            entity
            for entity in entities
            if entity_types.get(entity.id)
            == "TASK"
        ]

        if task_entities:
            task_names = [
                _safe_text(
                    entity.name
                ).strip()
                for entity in task_entities
                if entity.name
            ]

            if task_names:
                if len(task_names) == 1:
                    return (
                        "The task is "
                        f"{task_names[0]}."
                    )

                return (
                    "The tasks are "
                    + ", ".join(task_names)
                    + "."
                )

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
                    "The task is "
                    f"{contents[0]}."
                )

            return (
                "The tasks are "
                + ", ".join(contents)
                + "."
            )

        return None

    return None


def _run_secretary_answer(
    question: str,
    context: str,
) -> str:
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

Answer the user's question using ONLY the supplied information.

SUPPLIED INFORMATION:

{context}

USER QUESTION:

{question}

Rules:

1. Answer the question directly and naturally.
2. Use ONLY information explicitly present in SUPPLIED INFORMATION.
3. Never invent names, dates, amounts, tasks, meetings, events, reminders, responsibilities, or relationships.
4. If the answer is present in the supplied information, give it clearly.
5. If the answer is not present, say exactly:

I don't have that information in my memory.

6. For schedule questions, summarize relevant tasks, meetings, events, and reminders from the supplied information.
7. Keep the answer short.
8. Return ONLY the final answer.
9. Do not return JSON.
10. Do not return analysis or reasoning.
11. Do not repeat the question.

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

        if not answer:
            return (
                "I don't have that information "
                "in my memory."
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
            return (
                "I don't have that information "
                "in my memory."
            )

        return answer

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Gemma timed out after {timeout} seconds."
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


def _create_secretary_time_budget_plan(
    available_minutes: int,
    user_id: str,
    db: Session,
) -> dict:
    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id
        )
        .all()
    )

    return create_time_budget_plan(
        tasks=tasks,
        available_minutes=available_minutes,
    )


def _serialize_schedule(
    schedule,
):
    return {
        "date": schedule["date"],
        "tasks": [
            {
                "title": task.title,
                "deadline": (
                    task.deadline.isoformat()
                    if task.deadline
                    else None
                ),
                "status": task.status,
                "importance": task.importance,
                "priority_score": task.priority_score,
            }
            for task in schedule["tasks"]
        ],
        "meetings": [
            {
                "title": meeting.title,
                "start_time": (
                    meeting.start_time.isoformat()
                    if meeting.start_time
                    else None
                ),
                "end_time": (
                    meeting.end_time.isoformat()
                    if meeting.end_time
                    else None
                ),
                "location": meeting.location,
                "participants": meeting.participants,
            }
            for meeting in schedule["meetings"]
        ],
        "events": [
            {
                "event_type": event.event_type,
                "title": event.title,
                "description": event.description,
                "event_time": (
                    event.event_time.isoformat()
                    if event.event_time
                    else None
                ),
            }
            for event in schedule["events"]
        ],
        "reminders": [
            {
                "title": reminder.title,
                "message": reminder.message,
                "reminder_time": (
                    reminder.reminder_time.isoformat()
                    if reminder.reminder_time
                    else None
                ),
            }
            for reminder in schedule["reminders"]
        ],
        "counts": schedule["counts"],
    }


@router.post("/ask")
def ask_secretary(
    request: SecretaryAskRequest,
    db: Session = Depends(get_db),
):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    understanding = understand_question(
        question,
        use_gemma=False,
    )

    question_intent = understanding.get(
        "intent",
        "general_secretary_query",
    )

    target_date = understanding.get(
        "date"
    )

    if isinstance(
        target_date,
        str,
    ):
        try:
            target_date = date.fromisoformat(
                target_date
            )
        except ValueError:
            target_date = None

    if (
        question_intent
        in {
            "schedule_query",
            "meeting_query",
            "event_query",
            "task_query",
        }
        and target_date
    ):
        schedule = get_schedule_for_date(
            db=db,
            user_id=request.user_id,
            target_date=target_date,
        )

        schedule_data = _serialize_schedule(
            schedule
        )

        if question_intent == "meeting_query":
            schedule_data["tasks"] = []
            schedule_data["events"] = []
            schedule_data["reminders"] = []

        elif question_intent == "event_query":
            schedule_data["tasks"] = []
            schedule_data["meetings"] = []
            schedule_data["reminders"] = []

        elif question_intent == "task_query":
            schedule_data["meetings"] = []
            schedule_data["events"] = []
            schedule_data["reminders"] = []

        schedule_parts = []

        if schedule_data["tasks"]:
            task_text = ", ".join(
                task["title"]
                for task in schedule_data["tasks"]
            )

            schedule_parts.append(
                f"Tasks: {task_text}."
            )

        if schedule_data["meetings"]:
            meeting_text = ", ".join(
                meeting["title"]
                for meeting in schedule_data["meetings"]
            )

            schedule_parts.append(
                f"Meetings: {meeting_text}."
            )

        if schedule_data["events"]:
            event_text = ", ".join(
                event["title"]
                for event in schedule_data["events"]
            )

            schedule_parts.append(
                f"Events: {event_text}."
            )

        if schedule_data["reminders"]:
            reminder_text = ", ".join(
                reminder["title"]
                for reminder in schedule_data["reminders"]
            )

            schedule_parts.append(
                f"Reminders: {reminder_text}."
            )

        if schedule_parts:
            answer = (
                f"For {schedule_data['date']}, "
                "you have "
                + " ".join(
                    schedule_parts
                )
            )
        else:
            answer = (
                "You don't have anything "
                "scheduled for "
                f"{schedule_data['date']}."
            )

        return {
            "answer": answer,
            "sources": {
                "intent": question_intent,
                "answer_source": "schedule_retrieval",
                "date": schedule_data["date"],
                "tasks": len(
                    schedule_data["tasks"]
                ),
                "meetings": len(
                    schedule_data["meetings"]
                ),
                "events": len(
                    schedule_data["events"]
                ),
                "reminders": len(
                    schedule_data["reminders"]
                ),
            },
            "understanding": understanding,
        }

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

            answer = answer.replace(
                "usesall",
                "uses all",
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
                    "tasks_considered": plan.get(
                        "tasks_considered",
                        0,
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

    intent = _detect_secretary_intent(
        question
    )

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

    deterministic_answer = (
        _deterministic_secretary_answer(
            question=question,
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
                "entities": _count_entities(
                    db,
                    request.user_id,
                ),
                "facts": _count_facts(
                    db,
                    request.user_id,
                ),
                "relationships": _count_relationships(
                    db,
                    request.user_id,
                ),
                "events": _count_events(
                    db,
                    request.user_id,
                ),
                "memories": _count_memories(
                    db,
                    request.user_id,
                ),
                "intent": intent,
                "answer_source": (
                    "structured_memory"
                ),
            },
            "understanding": understanding,
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
            "entities": _count_entities(
                db,
                request.user_id,
            ),
            "facts": _count_facts(
                db,
                request.user_id,
            ),
            "relationships": _count_relationships(
                db,
                request.user_id,
            ),
            "events": _count_events(
                db,
                request.user_id,
            ),
            "memories": _count_memories(
                db,
                request.user_id,
            ),
            "intent": intent,
            "answer_source": "gemma",
        },
        "understanding": understanding,
    }