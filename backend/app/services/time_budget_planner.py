from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models.task import Task
from .priority import calculate_priority


# =========================================================
# Configuration
# =========================================================

# Kept for backward compatibility with older imports.
# Unknown-duration tasks now use the full remaining budget
# dynamically instead of being capped at 60 minutes.
UNKNOWN_DURATION_BLOCK_MINUTES = 60

# Avoid creating meaningless tiny work blocks when multiple
# tasks are being considered.
MIN_WORK_BLOCK_MINUTES = 10


# =========================================================
# Helpers
# =========================================================


def is_time_budget_request(message: str) -> bool:
    """
    Return True when a message asks what to work on
    based on an available-time budget.
    """
    if not message:
        return False

    q = str(message).lower().strip()

    has_time = bool(
        __import__("re").search(
            r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)\b",
            q,
        )
        or __import__("re").search(r"\b(?:an?|half|quarter)\s+hour\b", q)
        or __import__("re").search(r"\b\d+(?:\.\d+)?\s*hours?\s+\d+(?:\.\d+)?\s*(?:minutes?|mins?)\b", q)
    )

    planning_language = (
        "what should i work on" in q
        or "what should i do" in q
        or "what can i work on" in q
        or "what do i work on" in q
        or "what should i focus on" in q
        or "how should i use my time" in q
        or "how should i spend my time" in q
        or "what can i do" in q
        or "what task should i do" in q
        or "what tasks should i do" in q
    )

    return has_time and planning_language


def extract_available_minutes(message: str) -> Optional[int]:
    """
    Extract available time from natural language.

    Supports examples such as:
        5 minutes
        43 mins
        1 hour
        an hour
        1 hour 15 minutes
        2 hours 10 minutes
        1.5 hours
        half an hour
        quarter of an hour
    """
    import re

    if not message:
        return None

    q = str(message).lower().strip()

    if re.search(r"\bhalf\s+an?\s+hour\b", q):
        return 30

    if re.search(r"\bquarter\s+of\s+an?\s+hour\b", q):
        return 15

    # "an hour" / "a hour" — only when no numeric hour
    # expression is present.
    if re.search(r"\ban?\s+hour\b", q):
        if not re.search(
            r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?)\b",
            q,
        ):
            return 60

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)"
        r"\s*(?:and\s*)?"
        r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        q,
    )
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2))
        return round(hours * 60 + minutes)

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
        q,
    )
    if match:
        return round(float(match.group(1)) * 60)

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        q,
    )
    if match:
        return round(float(match.group(1)))

    return None


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

        if value == 0 and _task_status(task) != "completed":
            return 0

    if task.estimated_duration is not None:
        value = _safe_int(
            task.estimated_duration,
            default=0,
        )

        if value > 0:
            return value

    return None


def _task_status(
    task: Task,
) -> str:
    """
    Normalize task status.
    """
    return str(
        task.status or "pending"
    ).lower().strip()


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


def _progress_percent(
    task: Task,
) -> int:
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


def _deadline_pressure(
    task: Task,
) -> float:
    """
    Calculate additional deadline pressure.

    This is used only by the time-budget planner.
    The normal priority service remains unchanged.
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

    Existing priority calculation is preserved and
    additional time-budget signals are added.
    """

    priority = calculate_priority(task)

    score = float(
        priority.get(
            "score",
            0,
        )
    )

    # Deadline pressure is important when the user has
    # limited time.
    score += _deadline_pressure(task)

    # Continue work already in progress.
    if _task_status(task) == "in_progress":
        score += 15

    # Tasks with existing progress receive a small
    # continuity bonus.
    if _progress_percent(task) > 0:
        score += 5

    return score


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
# Task recommendation builder
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

    IMPORTANT:
    We do not invent the total duration.

    Instead, the planner assigns a bounded focused
    work block.
    """

    progress = _progress_percent(task)

    score = _calculate_budget_score(task)

    # Use all remaining available time as a focused work block.
    # This does not assume the task will be completed.
    work_block = max(
        1,
        int(available_minutes),
    )

    return {
        "task_id": task.id,
        "task_title": task.title,
        "recommendation": "work_unknown_duration",
        "reason": (
            "Task has no estimated duration. "
            f"Use the full {work_block}-minute available budget "
            "as a focused work block without assuming how long "
            "the entire task will take."
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

    Known-duration tasks that can be completed within
    the available budget are handled separately by the
    main planner.

    This function only performs the base priority sort.
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
    Create an intelligent work plan for a fixed
    amount of available time.

    Examples:

        20 minutes
        60 minutes
        180 minutes

    The planner supports:

    - complete tasks
    - partial tasks
    - multiple tasks
    - tasks with unknown duration
    - deadline pressure
    - existing progress
    - in-progress tasks
    - remaining task duration

    IMPORTANT:
    The planner recommends work allocation only.
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

        if remaining is not None and remaining > 0:
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
    # Recommendations
    # -----------------------------------------------------

    recommendations: List[
        Dict[str, Any]
    ] = []

    remaining_budget = available_minutes

    # =====================================================
    # Phase 1
    # Complete known-duration tasks that fit
    # =====================================================

    fitting_tasks: List[
        Tuple[float, Task]
    ] = []

    non_fitting_tasks: List[
        Tuple[float, Task]
    ] = []

    for score, task in known_scored:

        remaining = _remaining_minutes(
            task
        )

        if remaining is None:
            continue

        if remaining <= remaining_budget:
            fitting_tasks.append(
                (
                    score,
                    task,
                )
            )
        else:
            non_fitting_tasks.append(
                (
                    score,
                    task,
                )
            )

    # Higher priority first.
    fitting_tasks.sort(
        key=lambda item: (
            -item[0],
            item[1].deadline
            or datetime.max,
            item[1].id,
        )
    )

    for _, task in fitting_tasks:

        if remaining_budget <= 0:
            break

        remaining = _remaining_minutes(
            task
        )

        if remaining is None:
            continue

        if remaining <= 0:
            continue

        if remaining > remaining_budget:
            continue

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
            continue

        recommendations.append(
            recommendation
        )

        remaining_budget -= (
            recommended_minutes
        )

    # =====================================================
    # Phase 2
    # If time remains, continue with a high-priority
    # known-duration task that is longer than the budget.
    # =====================================================

    if remaining_budget > 0:

        candidates = []

        for score, task in non_fitting_tasks:

            remaining = _remaining_minutes(
                task
            )

            if remaining is None:
                continue

            if remaining <= 0:
                continue

            candidates.append(
                (
                    score,
                    task,
                    remaining,
                )
            )

        candidates.sort(
            key=lambda item: (
                -item[0],
                item[2],
                item[1].deadline
                or datetime.max,
                item[1].id,
            )
        )

        if candidates:

            _, task, _ = candidates[0]

            # Do not create tiny blocks when there are
            # multiple reasonable options.
            if (
                remaining_budget
                >= MIN_WORK_BLOCK_MINUTES
            ):

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

                    remaining_budget -= (
                        recommended_minutes
                    )

    # =====================================================
    # Phase 3
    # Unknown-duration task as a bounded fallback
    # =====================================================

    if remaining_budget > 0 and unknown_scored:

        # Choose the highest-priority unknown-duration task.
        _, task = unknown_scored[0]

        # If we already allocated work to known-duration
        # tasks, use the remaining budget up to the
        # configured maximum block.
        #
        # For a completely free budget, an unknown-duration
        # task can still be the first recommendation.
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

        if recommended_minutes > 0:

            recommendations.append(
                recommendation
            )

            remaining_budget -= (
                recommended_minutes
            )

    # =====================================================
    # Phase 4
    # If no recommendation was generated but we have a
    # known task, make one final bounded recommendation.
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

    # Safety normalization.
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
            "selected. Some time remains because the "
            "available tasks do not require or support "
            "additional work blocks."
        )

    # =====================================================
    # Final result
    # =====================================================

    return {
        "available_minutes": available_minutes,
        "tasks_considered": len(active_tasks),
        "recommendations": recommendations,
        "total_recommended_minutes": total_recommended,
        "remaining_budget_minutes": remaining_budget,
        "message": message,
    }

