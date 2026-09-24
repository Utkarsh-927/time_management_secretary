from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import re

from ..models.task import Task
from .priority import calculate_priority


# =========================================================
# Configuration
# =========================================================

# Maximum focused work block for ONE task whose duration
# is completely unknown.
UNKNOWN_DURATION_BLOCK_MINUTES = 60

# Avoid creating meaningless tiny work blocks.
MIN_WORK_BLOCK_MINUTES = 10


# =========================================================
# Basic helpers
# =========================================================

def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Safely convert a value to int.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _task_status(task: Task) -> str:
    """
    Normalize task status.
    """
    return str(
        task.status or "pending"
    ).lower().strip()


def _progress_percent(task: Task) -> int:
    """
    Return normalized progress percentage.
    """
    value = _safe_int(
        task.progress_percent,
        default=0,
    )

    return max(
        0,
        min(
            100,
            value,
        ),
    )


def _remaining_minutes(
    task: Task,
) -> Optional[int]:
    """
    Return the task's remaining work duration.

    Priority:
        1. remaining_duration
        2. estimated_duration
        3. None if duration is unknown
    """

    if task.remaining_duration is not None:

        value = _safe_int(
            task.remaining_duration,
            default=0,
        )

        if value > 0:
            return value

        if (
            value == 0
            and _task_status(task) != "completed"
        ):
            return 0

    if task.estimated_duration is not None:

        value = _safe_int(
            task.estimated_duration,
            default=0,
        )

        if value > 0:
            return value

    return None


def _is_active_task(
    task: Task,
) -> bool:
    """
    Determine whether a task can be considered
    by the time-budget planner.
    """

    status = _task_status(task)

    return status not in {
        "completed",
        "cancelled",
        "canceled",
        "deleted",
    }


def _duration_known(
    task: Task,
) -> bool:
    """
    Return True if the task has a usable duration.
    """

    remaining = _remaining_minutes(task)

    return (
        remaining is not None
        and remaining > 0
    )


# =========================================================
# Deadline / priority scoring
# =========================================================

def _deadline_pressure(
    task: Task,
) -> float:
    """
    Calculate additional deadline pressure.

    This is used only by the time-budget planner.
    """

    if task.deadline is None:
        return 0.0

    now = datetime.now()

    remaining_hours = (
        task.deadline - now
    ).total_seconds() / 3600

    # Already overdue.
    if remaining_hours < 0:
        return 100.0

    # Due within 6 hours.
    if remaining_hours <= 6:
        return 90.0

    # Due within 24 hours.
    if remaining_hours <= 24:
        return 70.0

    # Due within 3 days.
    if remaining_hours <= 72:
        return 50.0

    # Due within 7 days.
    if remaining_hours <= 168:
        return 25.0

    return 0.0


def _calculate_budget_score(
    task: Task,
) -> float:
    """
    Calculate how suitable a task is for the
    available-time planner.
    """

    try:
        priority = calculate_priority(task)

    except Exception:
        priority = {}

    score = float(
        priority.get(
            "score",
            0,
        )
    )

    # Deadline pressure.
    score += _deadline_pressure(task)

    # Continue work already in progress.
    if _task_status(task) == "in_progress":
        score += 15

    # Continuity bonus.
    if _progress_percent(task) > 0:
        score += 5

    return score


# =========================================================
# Natural-language time extraction
# =========================================================

def extract_available_minutes(
    message: str,
) -> Optional[int]:
    """
    Extract available work time from natural language.

    Supported examples:

        20 minutes
        30 min
        1 minute
        1 hour
        2 hours
        1 hr
        2 hrs
        1 hour 30 minutes
        1 hr 30 min
        1.5 hours
        half an hour
        quarter of an hour
    """

    if not message:
        return None

    text = message.lower().strip()

    # -----------------------------------------------------
    # Combined hour + minute
    #
    # 1 hour 30 minutes
    # 1 hr 30 min
    # 1 hour and 30 minutes
    # -----------------------------------------------------

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)"
        r"\s*(?:and\s*)?"
        r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        text,
    )

    if match:

        hours = float(
            match.group(1)
        )

        minutes = float(
            match.group(2)
        )

        return round(
            hours * 60 + minutes
        )

    # -----------------------------------------------------
    # Half an hour
    # -----------------------------------------------------

    if re.search(
        r"\bhalf\s+an?\s+hour\b",
        text,
    ):
        return 30

    # -----------------------------------------------------
    # Quarter of an hour
    # -----------------------------------------------------

    if re.search(
        r"\bquarter\s+of\s+an?\s+hour\b",
        text,
    ):
        return 15

    # -----------------------------------------------------
    # Hours
    # -----------------------------------------------------

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
        text,
    )

    if match:

        return round(
            float(
                match.group(1)
            ) * 60
        )

    # -----------------------------------------------------
    # Minutes
    # -----------------------------------------------------

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        text,
    )

    if match:

        return round(
            float(
                match.group(1)
            )
        )

    return None


def is_time_budget_request(
    message: str,
) -> bool:
    """
    Detect whether a natural-language message is asking
    what work should be done within a stated time budget.
    """

    if not message:
        return False

    text = message.lower().strip()

    available_minutes = extract_available_minutes(
        text
    )

    if available_minutes is None:
        return False

    # -----------------------------------------------------
    # Direct planning questions
    # -----------------------------------------------------

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
        "what should i focus",
        "what can i focus on",
        "what is the best use of my time",
        "how should i use my time",
        "how can i use my time",
        "what should i spend my time on",
        "which task can i do",
    )

    if any(
        phrase in text
        for phrase in planning_phrases
    ):
        return True

    # -----------------------------------------------------
    # Natural statements
    #
    # I have 20 minutes
    # I've got 1 hour
    # I got 30 minutes
    # -----------------------------------------------------

    if re.search(
        r"\b(i\s+have|i've\s+got|i\s+got)\b",
        text,
    ):
        return True

    # -----------------------------------------------------
    # 20 minutes free
    # 30 minutes available
    # 2 hours free
    # -----------------------------------------------------

    if re.search(
        r"\b(?:minutes?|mins?|hours?|hrs?)\s+"
        r"(?:free|available)\b",
        text,
    ):
        return True

    # -----------------------------------------------------
    # I am free for 20 minutes
    # I'm available for 1 hour
    # -----------------------------------------------------

    if re.search(
        r"\b(?:i\s+am|i'm)\s+"
        r"(?:free|available)\s+for\b",
        text,
    ):
        return True

    return False


# =========================================================
# Recommendation builders
# =========================================================

def _build_known_duration_recommendation(
    task: Task,
    available_minutes: int,
) -> Dict[str, Any]:
    """
    Build a recommendation for a task whose remaining
    duration is known.
    """

    remaining = _remaining_minutes(task)

    progress = _progress_percent(task)

    score = _calculate_budget_score(task)

    if remaining is None:

        raise ValueError(
            "Known-duration recommendation received "
            "a task with unknown duration."
        )

    if remaining <= 0:

        return {
            "task_id": task.id,
            "task_title": task.title,
            "recommendation": "skip",
            "reason": "Task has no remaining work.",
            "available_minutes": available_minutes,
            "remaining_minutes": 0,
            "recommended_minutes": 0,
            "partial": False,
            "progress_before": progress,
            "progress_after": 100,
            "priority_score": score,
            "deadline": task.deadline,
            "status": task.status,
        }

    work_minutes = min(
        available_minutes,
        remaining,
    )

    partial = (
        work_minutes < remaining
    )

    estimated_total = None

    if task.estimated_duration is not None:

        estimated_total = max(
            1,
            _safe_int(
                task.estimated_duration,
                default=1,
            ),
        )

    if estimated_total:

        progress_gain = (
            work_minutes
            / estimated_total
        ) * 100

        progress_after = min(
            100,
            round(
                progress
                + progress_gain
            ),
        )

    else:

        progress_after = progress

    if partial:

        reason = (
            "This task is longer than the available "
            "time, so use the available time to make "
            "partial progress."
        )

    else:

        reason = (
            "This task can be completed within "
            "the available time."
        )

    return {
        "task_id": task.id,
        "task_title": task.title,
        "recommendation": "work",
        "reason": reason,
        "available_minutes": available_minutes,
        "remaining_minutes": remaining,
        "recommended_minutes": work_minutes,
        "partial": partial,
        "progress_before": progress,
        "progress_after": progress_after,
        "priority_score": score,
        "deadline": task.deadline,
        "status": task.status,
    }


def _build_unknown_duration_recommendation(
    task: Task,
    available_minutes: int,
) -> Dict[str, Any]:
    """
    Build a recommendation for a task whose duration
    is unknown.

    We do not invent the total duration.

    Instead, assign one bounded focused work block.
    """

    progress = _progress_percent(task)

    score = _calculate_budget_score(task)

    work_block = min(
        available_minutes,
        UNKNOWN_DURATION_BLOCK_MINUTES,
    )

    return {
        "task_id": task.id,
        "task_title": task.title,
        "recommendation": "work_unknown_duration",
        "reason": (
            "Task has no estimated duration. "
            f"Use a focused {work_block}-minute work block "
            "without assuming how long the entire task "
            "will take."
        ),
        "available_minutes": available_minutes,
        "remaining_minutes": None,
        "recommended_minutes": work_block,
        "partial": True,
        "progress_before": progress,
        "progress_after": progress,
        "priority_score": score,
        "deadline": task.deadline,
        "status": task.status,
    }


def _build_task_recommendation(
    task: Task,
    available_minutes: int,
) -> Dict[str, Any]:
    """
    Build a recommendation based on whether the task
    has known or unknown duration.
    """

    remaining = _remaining_minutes(task)

    if remaining is not None:

        return _build_known_duration_recommendation(
            task,
            available_minutes,
        )

    return _build_unknown_duration_recommendation(
        task,
        available_minutes,
    )


# =========================================================
# Task sorting
# =========================================================

def _sort_tasks(
    tasks: List[Task],
) -> List[Tuple[float, Task]]:
    """
    Score and sort active tasks.

    Higher score comes first.

    Earlier deadlines are used as a tie-breaker.
    """

    scored_tasks: List[
        Tuple[float, Task]
    ] = []

    for task in tasks:

        score = _calculate_budget_score(
            task
        )

        scored_tasks.append(
            (
                score,
                task,
            )
        )

    scored_tasks.sort(
        key=lambda item: (
            -item[0],
            item[1].deadline
            or datetime.max,
            item[1].id,
        )
    )

    return scored_tasks


# =========================================================
# Main time-budget planner
# =========================================================

def create_time_budget_plan(
    tasks: List[Task],
    available_minutes: int,
) -> Dict[str, Any]:
    """
    Create an intelligent multi-task work plan.

    Supports:

        - complete tasks
        - partial tasks
        - multiple tasks
        - unknown-duration tasks
        - deadline pressure
        - existing progress
        - in-progress tasks
        - remaining duration

    IMPORTANT:

    This function only recommends work allocation.

    It does NOT modify task progress in the database.
    """

    available_minutes = _safe_int(
        available_minutes,
        default=0,
    )

    # -----------------------------------------------------
    # Invalid budget
    # -----------------------------------------------------

    if available_minutes <= 0:

        return {
            "available_minutes": available_minutes,
            "tasks_considered": 0,
            "recommendations": [],
            "total_recommended_minutes": 0,
            "remaining_budget_minutes": available_minutes,
            "message": (
                "Available time must be greater than zero."
            ),
        }

    # -----------------------------------------------------
    # Active tasks only
    # -----------------------------------------------------

    active_tasks = [
        task
        for task in tasks
        if _is_active_task(task)
    ]

    if not active_tasks:

        return {
            "available_minutes": available_minutes,
            "tasks_considered": 0,
            "recommendations": [],
            "total_recommended_minutes": 0,
            "remaining_budget_minutes": available_minutes,
            "message": (
                "No active tasks are currently available "
                "for this time budget."
            ),
        }

    # -----------------------------------------------------
    # Separate known and unknown duration tasks
    # -----------------------------------------------------

    known_duration_tasks: List[Task] = []
    unknown_duration_tasks: List[Task] = []

    for task in active_tasks:

        remaining = _remaining_minutes(task)

        if (
            remaining is not None
            and remaining > 0
        ):

            known_duration_tasks.append(task)

        elif remaining is None:

            unknown_duration_tasks.append(task)

    # -----------------------------------------------------
    # Score tasks
    # -----------------------------------------------------

    known_scored = _sort_tasks(
        known_duration_tasks
    )

    unknown_scored = _sort_tasks(
        unknown_duration_tasks
    )

    # -----------------------------------------------------
    # Planning state
    # -----------------------------------------------------

    recommendations: List[
        Dict[str, Any]
    ] = []

    remaining_budget = available_minutes

    # Keep track of tasks already recommended.
    recommended_task_ids = set()

    # =====================================================
    # PHASE 1
    #
    # Complete as many known-duration tasks as possible.
    #
    # Example:
    #
    # Budget = 120
    #
    # Task A = 30
    # Task B = 40
    # Task C = 90
    #
    # Result:
    #
    # Task A = 30
    # Task B = 40
    # Task C = 50 partial
    # =====================================================

    while remaining_budget > 0:

        fitting_candidates = []

        for score, task in known_scored:

            if task.id in recommended_task_ids:
                continue

            remaining = _remaining_minutes(
                task
            )

            if remaining is None:
                continue

            if remaining <= 0:
                continue

            if remaining <= remaining_budget:

                fitting_candidates.append(
                    (
                        score,
                        task,
                        remaining,
                    )
                )

        if not fitting_candidates:
            break

        # Highest priority first.
        fitting_candidates.sort(
            key=lambda item: (
                -item[0],
                item[2],
                item[1].deadline
                or datetime.max,
                item[1].id,
            )
        )

        _, task, _ = fitting_candidates[0]

        recommendation = (
            _build_known_duration_recommendation(
                task,
                remaining_budget,
            )
        )

        recommended_minutes = _safe_int(
            recommendation.get(
                "recommended_minutes"
            ),
            default=0,
        )

        if recommended_minutes <= 0:
            break

        recommendations.append(
            recommendation
        )

        recommended_task_ids.add(
            task.id
        )

        remaining_budget -= (
            recommended_minutes
        )

    # =====================================================
    # PHASE 2
    #
    # If time remains, use the remaining budget on the
    # highest-priority known-duration task.
    #
    # This allows partial progress.
    # =====================================================

    if remaining_budget >= MIN_WORK_BLOCK_MINUTES:

        partial_candidates = []

        for score, task in known_scored:

            if task.id in recommended_task_ids:
                continue

            remaining = _remaining_minutes(
                task
            )

            if remaining is None:
                continue

            if remaining <= remaining_budget:
                continue

            if remaining <= 0:
                continue

            partial_candidates.append(
                (
                    score,
                    task,
                    remaining,
                )
            )

        partial_candidates.sort(
            key=lambda item: (
                -item[0],
                item[2],
                item[1].deadline
                or datetime.max,
                item[1].id,
            )
        )

        if partial_candidates:

            _, task, _ = (
                partial_candidates[0]
            )

            recommendation = (
                _build_known_duration_recommendation(
                    task,
                    remaining_budget,
                )
            )

            recommended_minutes = _safe_int(
                recommendation.get(
                    "recommended_minutes"
                ),
                default=0,
            )

            if recommended_minutes > 0:

                recommendations.append(
                    recommendation
                )

                recommended_task_ids.add(
                    task.id
                )

                remaining_budget -= (
                    recommended_minutes
                )

    # =====================================================
    # PHASE 3
    #
    # Use multiple unknown-duration tasks.
    #
    # IMPORTANT:
    #
    # Each unknown-duration task gets at most
    # UNKNOWN_DURATION_BLOCK_MINUTES.
    #
    # We never assume the full duration of the task.
    #
    # Example:
    #
    # Budget = 120
    #
    # Unknown Task A → 60
    # Unknown Task B → 60
    #
    # Total = 120
    # =====================================================

    if (
        remaining_budget > 0
        and unknown_scored
    ):

        for _, task in unknown_scored:

            if remaining_budget <= 0:
                break

            if task.id in recommended_task_ids:
                continue

            # If only a tiny amount remains, do not create
            # a meaningless block.
            if (
                remaining_budget
                < MIN_WORK_BLOCK_MINUTES
            ):
                break

            recommendation = (
                _build_unknown_duration_recommendation(
                    task,
                    remaining_budget,
                )
            )

            recommended_minutes = _safe_int(
                recommendation.get(
                    "recommended_minutes"
                ),
                default=0,
            )

            if recommended_minutes <= 0:
                continue

            recommendations.append(
                recommendation
            )

            recommended_task_ids.add(
                task.id
            )

            remaining_budget -= (
                recommended_minutes
            )

    # =====================================================
    # PHASE 4
    #
    # Final fallback.
    #
    # This mainly protects against unusual task data.
    # =====================================================

    if (
        not recommendations
        and known_scored
        and available_minutes > 0
    ):

        _, task = known_scored[0]

        recommendation = (
            _build_task_recommendation(
                task,
                available_minutes,
            )
        )

        recommended_minutes = _safe_int(
            recommendation.get(
                "recommended_minutes"
            ),
            default=0,
        )

        if recommended_minutes > 0:

            recommendations.append(
                recommendation
            )

            remaining_budget -= (
                recommended_minutes
            )

    # =====================================================
    # Calculate totals
    # =====================================================

    total_recommended = (
        available_minutes
        - remaining_budget
    )

    if total_recommended < 0:
        total_recommended = 0

    if remaining_budget < 0:
        remaining_budget = 0

    # =====================================================
    # Human-readable summary
    # =====================================================

    if not recommendations:

        message = (
            "No active tasks are currently available "
            "for this time budget."
        )

    elif remaining_budget == 0:

        message = (
            "Your available time has been fully allocated "
            "across the highest-priority suitable work."
        )

    else:

        message = (
            "The highest-priority suitable work has been "
            "selected. Some time remains because there "
            "are not enough suitable tasks to allocate "
            "the entire time budget."
        )

    # =====================================================
    # Final result
    # =====================================================

    return {
        "available_minutes": available_minutes,
        "tasks_considered": len(
            active_tasks
        ),
        "recommendations": recommendations,
        "total_recommended_minutes": (
            total_recommended
        ),
        "remaining_budget_minutes": (
            remaining_budget
        ),
        "message": message,
    }