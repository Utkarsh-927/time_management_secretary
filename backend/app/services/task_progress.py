from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.task import Task


# =========================================================
# Configuration
# =========================================================

MIN_PROGRESS_PERCENT = 0
MAX_PROGRESS_PERCENT = 100

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "on",
    "of",
    "in",
    "with",
    "my",
    "this",
    "that",
    "is",
    "was",
    "were",
    "be",
    "been",
    "i",
    "ive",
    "i've",
    "it",
    "task",
    "work",
    "worked",
}


# =========================================================
# Basic helpers
# =========================================================

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).lower().strip()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _tokens(text: str) -> List[str]:
    normalized = _normalize_text(text)

    return [
        token
        for token in normalized.split()
        if token and token not in STOP_WORDS
    ]


def _progress_percent(task: Task) -> int:
    value = _safe_int(
        task.progress_percent,
        default=0,
    )

    return max(
        MIN_PROGRESS_PERCENT,
        min(
            MAX_PROGRESS_PERCENT,
            value,
        ),
    )


def _remaining_minutes(task: Task) -> Optional[int]:
    if task.remaining_duration is not None:
        value = _safe_int(
            task.remaining_duration,
            default=0,
        )

        if value > 0:
            return value

        if value == 0:
            return 0

    if task.estimated_duration is not None:
        value = _safe_int(
            task.estimated_duration,
            default=0,
        )

        if value > 0:
            return value

    return None


def _is_active(task: Task) -> bool:
    status = str(
        task.status or "pending"
    ).lower().strip()

    return status not in {
        "completed",
        "cancelled",
        "canceled",
        "deleted",
    }


# =========================================================
# Detect progress action
# =========================================================

def detect_progress_action(message: str) -> Optional[str]:
    """
    Detect whether a natural-language message represents
    task progress.

    Returns:

        "worked"
        "completed"
        None
    """

    text = _normalize_text(message)

    # -----------------------------------------------------
    # Completion phrases
    # -----------------------------------------------------

    completion_patterns = [
        r"\bfinished\b",
        r"\bcompleted\b",
        r"\bcomplete\b",
        r"\bdone\b",
        r"\bwrapped up\b",
        r"\bfinalized\b",
    ]

    for pattern in completion_patterns:
        if re.search(pattern, text):
            return "completed"

    # -----------------------------------------------------
    # Work/progress phrases
    # -----------------------------------------------------

    work_patterns = [
        r"\bworked\b",
        r"\bwork(ed)?\s+on\b",
        r"\bspent\b",
        r"\bspent\s+\d+\s+(?:minutes?|mins?|hours?|hrs?)\b",
        r"\bworked\s+for\b",
        r"\bmade\s+progress\b",
        r"\bmade\s+some\s+progress\b",
    ]

    for pattern in work_patterns:
        if re.search(pattern, text):
            return "worked"

    return None


# =========================================================
# Extract worked duration
# =========================================================

def extract_work_duration(message: str) -> Optional[int]:
    """
    Extract the amount of time the user says they worked.

    Examples:

        "worked for 30 minutes" -> 30
        "worked 1 hour" -> 60
        "spent 1.5 hours" -> 90
        "worked for 45 mins" -> 45
    """

    text = message.lower().strip()

    # -----------------------------------------------------
    # Decimal / integer hours
    # -----------------------------------------------------

    hour_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*"
        r"(?:hours?|hrs?|hr|h)\b",
        text,
    )

    if hour_match:
        hours = float(
            hour_match.group(1)
        )

        minutes = round(
            hours * 60
        )

        if minutes > 0:
            return minutes

    # -----------------------------------------------------
    # Minutes
    # -----------------------------------------------------

    minute_match = re.search(
        r"\b(\d+)\s*"
        r"(?:minutes?|mins?|min|m)\b",
        text,
    )

    if minute_match:
        minutes = int(
            minute_match.group(1)
        )

        if minutes > 0:
            return minutes

    return None


# =========================================================
# Extract explicit progress percentage
# =========================================================

def extract_progress_percent(
    message: str,
) -> Optional[int]:
    """
    Extract explicit progress percentages.

    Examples:

        "I'm 50% done"
        "task is 75 percent complete"
    """

    text = message.lower()

    percent_match = re.search(
        r"\b(\d{1,3})\s*%\b",
        text,
    )

    if percent_match:
        value = int(
            percent_match.group(1)
        )

        return max(
            0,
            min(
                100,
                value,
            ),
        )

    percent_word_match = re.search(
        r"\b(\d{1,3})\s*percent\b",
        text,
    )

    if percent_word_match:
        value = int(
            percent_word_match.group(1)
        )

        return max(
            0,
            min(
                100,
                value,
            ),
        )

    return None


# =========================================================
# Extract task reference
# =========================================================

def _candidate_texts(message: str) -> List[str]:
    """
    Produce useful pieces of the user's message for
    task matching.
    """

    candidates = [
        message,
    ]

    patterns = [
        r"\bwork(?:ed)?\s+(?:on|for)\s+(.+?)(?:\s+for\s+\d+|\s+today|\s*$)",
        r"\bspent\s+\d+.*?\s+on\s+(.+)$",
        r"\bfinished\s+(.+)$",
        r"\bcompleted\s+(.+)$",
        r"\bcomplete(?:d)?\s+(.+)$",
        r"\bdone\s+with\s+(.+)$",
        r"\bfinished\s+working\s+on\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            message,
            flags=re.IGNORECASE,
        )

        if match:
            candidates.append(
                match.group(1).strip()
            )

    return candidates


# =========================================================
# Task matching
# =========================================================

def _task_match_score(
    task: Task,
    message: str,
) -> float:
    """
    Calculate how strongly a task matches the message.
    """

    title_tokens = set(
        _tokens(task.title)
    )

    if not title_tokens:
        return 0.0

    candidate_texts = _candidate_texts(
        message
    )

    best_score = 0.0

    for candidate in candidate_texts:
        candidate_tokens = set(
            _tokens(candidate)
        )

        if not candidate_tokens:
            continue

        overlap = (
            title_tokens
            & candidate_tokens
        )

        if not overlap:
            continue

        # Percentage of task title tokens that
        # were found in the message.
        coverage = (
            len(overlap)
            / len(title_tokens)
        )

        # Percentage of candidate tokens that
        # belong to the task title.
        precision = (
            len(overlap)
            / len(candidate_tokens)
        )

        score = (
            coverage * 70
            + precision * 30
        )

        best_score = max(
            best_score,
            score,
        )

    # Exact title occurrence is extremely strong.
    normalized_message = _normalize_text(
        message
    )

    normalized_title = _normalize_text(
        task.title
    )

    if normalized_title and normalized_title in normalized_message:
        best_score = max(
            best_score,
            100.0,
        )

    return best_score


def find_matching_task(
    tasks: List[Task],
    message: str,
) -> Tuple[Optional[Task], float]:
    """
    Find the best active task matching the user's
    natural-language update.
    """

    candidates: List[
        Tuple[float, Task]
    ] = []

    for task in tasks:

        if not _is_active(task):
            continue

        score = _task_match_score(
            task,
            message,
        )

        if score > 0:
            candidates.append(
                (
                    score,
                    task,
                )
            )

    if not candidates:
        return None, 0.0

    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1].id,
        )
    )

    score, task = candidates[0]

    # Require meaningful confidence.
    if score < 25:
        return None, score

    return task, score


# =========================================================
# Apply work duration
# =========================================================

def _apply_work_duration(
    task: Task,
    worked_minutes: int,
) -> Dict[str, Any]:
    """
    Apply a worked-time update to a task.

    IMPORTANT:
    This function modifies the SQLAlchemy object but
    does not commit the database transaction.
    """

    worked_minutes = max(
        1,
        _safe_int(
            worked_minutes,
            default=0,
        ),
    )

    progress_before = _progress_percent(
        task
    )

    remaining_before = _remaining_minutes(
        task
    )

    # -----------------------------------------------------
    # Unknown-duration task
    # -----------------------------------------------------

    if remaining_before is None:

        task.status = "in_progress"

        if task.started_at is None:
            task.started_at = datetime.utcnow()

        task.updated_at = datetime.utcnow()

        return {
            "task_id": task.id,
            "task_title": task.title,
            "action": "worked",
            "worked_minutes": worked_minutes,
            "progress_before": progress_before,
            "progress_after": progress_before,
            "remaining_minutes_before": None,
            "remaining_minutes_after": None,
            "duration_known": False,
            "status": task.status,
        }

    # -----------------------------------------------------
    # Known-duration task
    # -----------------------------------------------------

    remaining_after = max(
        0,
        remaining_before - worked_minutes,
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

    if estimated_total is not None:

        progress_gain = (
            worked_minutes
            / estimated_total
        ) * 100

        progress_after = min(
            100,
            round(
                progress_before
                + progress_gain
            ),
        )

    else:

        # If estimated duration does not exist but
        # remaining duration does, preserve existing
        # progress rather than inventing a percentage.
        progress_after = progress_before

    # -----------------------------------------------------
    # Completed
    # -----------------------------------------------------

    if remaining_after <= 0:

        task.remaining_duration = 0
        task.progress_percent = 100
        task.status = "completed"
        task.completed_at = (
            datetime.utcnow()
        )

        if task.started_at is None:
            task.started_at = (
                datetime.utcnow()
            )

    # -----------------------------------------------------
    # Still in progress
    # -----------------------------------------------------

    else:

        task.remaining_duration = (
            remaining_after
        )

        task.progress_percent = (
            progress_after
        )

        task.status = "in_progress"

        if task.started_at is None:
            task.started_at = (
                datetime.utcnow()
            )

        task.completed_at = None

    task.updated_at = datetime.utcnow()

    return {
        "task_id": task.id,
        "task_title": task.title,
        "action": (
            "completed"
            if task.status == "completed"
            else "worked"
        ),
        "worked_minutes": worked_minutes,
        "progress_before": progress_before,
        "progress_after": task.progress_percent,
        "remaining_minutes_before": remaining_before,
        "remaining_minutes_after": task.remaining_duration,
        "duration_known": True,
        "status": task.status,
    }


# =========================================================
# Apply completion
# =========================================================

def _apply_completion(
    task: Task,
) -> Dict[str, Any]:
    """
    Mark a task as completed.
    """

    progress_before = _progress_percent(
        task
    )

    remaining_before = _remaining_minutes(
        task
    )

    now = datetime.utcnow()

    task.progress_percent = 100
    task.remaining_duration = 0
    task.status = "completed"
    task.completed_at = now
    task.updated_at = now

    if task.started_at is None:
        task.started_at = now

    return {
        "task_id": task.id,
        "task_title": task.title,
        "action": "completed",
        "worked_minutes": None,
        "progress_before": progress_before,
        "progress_after": 100,
        "remaining_minutes_before": remaining_before,
        "remaining_minutes_after": 0,
        "duration_known": (
            remaining_before is not None
        ),
        "status": "completed",
    }


# =========================================================
# Main processor
# =========================================================

def process_task_progress(
    db: Session,
    user_id: str,
    message: str,
) -> Optional[Dict[str, Any]]:
    """
    Detect and apply a natural-language task progress
    update.

    Returns None when the message does not appear to be
    a task-progress update.

    The database transaction is committed only when a
    matching task is successfully updated.
    """

    if not message or not message.strip():
        return None

    action = detect_progress_action(
        message
    )

    if action is None:
        return None

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id
        )
        .all()
    )

    task, match_score = find_matching_task(
        tasks,
        message,
    )

    if task is None:
        return {
            "updated": False,
            "action": action,
            "task_id": None,
            "task_title": None,
            "match_score": match_score,
            "message": (
                "I understood this as a task progress "
                "update, but I could not confidently "
                "identify which task you mean."
            ),
        }

    # -----------------------------------------------------
    # Explicit completion
    # -----------------------------------------------------

    if action == "completed":

        result = _apply_completion(
            task
        )

        db.commit()
        db.refresh(task)

        return {
            "updated": True,
            "match_score": match_score,
            **result,
            "message": (
                f"Marked '{task.title}' as completed."
            ),
        }

    # -----------------------------------------------------
    # Worked-time update
    # -----------------------------------------------------

    worked_minutes = (
        extract_work_duration(
            message
        )
    )

    explicit_progress = (
        extract_progress_percent(
            message
        )
    )

    # If the user gave a percentage directly,
    # use that instead of guessing from time.
    if explicit_progress is not None:

        progress_before = _progress_percent(
            task
        )

        task.progress_percent = (
            explicit_progress
        )

        if explicit_progress >= 100:

            task.progress_percent = 100
            task.remaining_duration = 0
            task.status = "completed"
            task.completed_at = (
                datetime.utcnow()
            )

        else:

            task.status = "in_progress"

            if task.started_at is None:
                task.started_at = (
                    datetime.utcnow()
                )

            task.completed_at = None

        task.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(task)

        return {
            "updated": True,
            "match_score": match_score,
            "task_id": task.id,
            "task_title": task.title,
            "action": (
                "completed"
                if explicit_progress >= 100
                else "progress_updated"
            ),
            "worked_minutes": worked_minutes,
            "progress_before": progress_before,
            "progress_after": task.progress_percent,
            "remaining_minutes_after": task.remaining_duration,
            "status": task.status,
            "message": (
                f"Updated '{task.title}' to "
                f"{task.progress_percent}% progress."
            ),
        }

    # -----------------------------------------------------
    # No duration supplied
    # -----------------------------------------------------

    if worked_minutes is None:

        return {
            "updated": False,
            "action": action,
            "task_id": task.id,
            "task_title": task.title,
            "match_score": match_score,
            "message": (
                f"I identified '{task.title}', but "
                "you didn't specify how much work you "
                "completed. You can say something like "
                "'I worked on it for 30 minutes.'"
            ),
        }

    # -----------------------------------------------------
    # Apply worked duration
    # -----------------------------------------------------

    result = _apply_work_duration(
        task,
        worked_minutes,
    )

    db.commit()
    db.refresh(task)

    if result["status"] == "completed":

        message_text = (
            f"'{task.title}' is now completed."
        )

    elif result["duration_known"]:

        message_text = (
            f"Recorded {worked_minutes} minutes on "
            f"'{task.title}'. "
            f"{task.remaining_duration} minutes remain."
        )

    else:

        message_text = (
            f"Recorded {worked_minutes} minutes on "
            f"'{task.title}'. Its total duration is "
            "still unknown, so I did not invent a "
            "remaining duration or progress percentage."
        )

    return {
        "updated": True,
        "match_score": match_score,
        **result,
        "message": message_text,
    }