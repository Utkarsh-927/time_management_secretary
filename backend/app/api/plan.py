from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.task import Task
from ..models.availability import Availability
from ..models.meeting import Meeting
from ..services.planner import create_plan
from ..services.time_budget_planner import create_time_budget_plan


router = APIRouter(
    prefix="/plan",
    tags=["Planning"],
)


def _normalize_minutes(value: int) -> int:
    """Keep planner input safe."""
    return max(0, int(value))


def _extract_available_minutes(message: str) -> Optional[int]:
    """
    Extract available time from natural language.

    Examples:
        20 minutes
        30 min
        1 hour
        2 hours
        1 hour 30 minutes
        one hour
        half an hour
    """

    text = message.lower().strip()

    # 1 hour 30 minutes
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)"
        r"\s*(?:and\s*)?"
        r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        text,
    )

    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2))
        return round(hours * 60 + minutes)

    # Hours only
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
        text,
    )

    if match:
        return round(float(match.group(1)) * 60)

    # Minutes only
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        text,
    )

    if match:
        return round(float(match.group(1)))

    # Common natural language
    if re.search(r"\bhalf an hour\b", text):
        return 30

    if re.search(r"\bquarter of an hour\b", text):
        return 15

    return None


def _is_time_budget_request(message: str) -> bool:
    """
    Detect whether the user is asking for a
    time-budget-based work recommendation.
    """

    text = message.lower()

    has_time = _extract_available_minutes(text) is not None

    if not has_time:
        return False

    planning_phrases = (
        "what should i do",
        "what should i work on",
        "what can i do",
        "what do i work on",
        "what task should i do",
        "what task should i work on",
        "which task",
        "what should i focus on",
        "what can i work on",
        "i have",
        "i've got",
        "i got",
        "free time",
        "available time",
        "minutes free",
        "hours free",
        "time available",
    )

    return any(phrase in text for phrase in planning_phrases)


@router.get("")
def get_plan(
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    """
    Generate the existing complete time-management plan.
    """

    tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .all()
    )

    availability = (
        db.query(Availability)
        .filter(Availability.user_id == user_id)
        .all()
    )

    meetings = (
        db.query(Meeting)
        .filter(Meeting.user_id == user_id)
        .all()
    )

    result = create_plan(
        tasks,
        availability,
        meetings,
    )

    return {
        "message": "Plan generated successfully",
        "user_id": user_id,
        "data": result,
    }


@router.get("/time-budget")
def get_time_budget_plan(
    available_minutes: int = Query(
        ...,
        ge=1,
        description="Available focused work time in minutes.",
    ),
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    """
    Generate a work recommendation for a fixed amount
    of available time.

    Example:
        /plan/time-budget?available_minutes=20&user_id=default
    """

    tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .all()
    )

    result = create_time_budget_plan(
        tasks=tasks,
        available_minutes=_normalize_minutes(
            available_minutes
        ),
    )

    return {
        "message": "Time-budget plan generated successfully",
        "user_id": user_id,
        "data": result,
    }


@router.post("/natural")
def natural_time_budget_plan(
    message: str = Query(
        ...,
        min_length=1,
        description="Natural-language time planning request.",
    ),
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    """
    Convert natural-language available time into a planner request.

    Examples:
        I have 20 minutes. What should I do?
        I have 1 hour free.
        I have 2 hours. What should I work on?
    """

    minutes = _extract_available_minutes(message)

    if minutes is None:
        return {
            "message": (
                "I could not determine how much time "
                "you have available."
            ),
            "user_id": user_id,
            "detected_minutes": None,
            "data": None,
        }

    tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .all()
    )

    result = create_time_budget_plan(
        tasks=tasks,
        available_minutes=minutes,
    )

    return {
        "message": "Natural-language time plan generated successfully",
        "user_id": user_id,
        "input": message,
        "detected_minutes": minutes,
        "data": result,
    }