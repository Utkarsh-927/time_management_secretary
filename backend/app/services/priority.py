from datetime import datetime


# ============================================================
# PRIORITY LABEL
# ============================================================

def get_priority_label(score: int) -> str:
    """
    Convert a numerical priority score
    into a human-readable priority label.
    """

    if score >= 100:
        return "CRITICAL"

    if score >= 75:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    return "LOW"


# ============================================================
# DEADLINE SCORE
# ============================================================

def calculate_deadline_score(deadline):
    """
    Calculate urgency based on the amount of time
    remaining until the deadline.

    Overdue tasks receive the strongest urgency.
    """

    if deadline is None:
        return 0

    now = datetime.now()

    # --------------------------------------------------------
    # Calculate remaining time
    # --------------------------------------------------------

    remaining_hours = (
        deadline - now
    ).total_seconds() / 3600

    # --------------------------------------------------------
    # OVERDUE
    # --------------------------------------------------------

    if remaining_hours < 0:

        overdue_hours = abs(
            remaining_hours
        )

        if overdue_hours >= 72:
            return 60

        if overdue_hours >= 24:
            return 55

        return 50

    # --------------------------------------------------------
    # VERY URGENT
    # --------------------------------------------------------

    if remaining_hours <= 6:
        return 45

    # --------------------------------------------------------
    # DUE WITHIN 24 HOURS
    # --------------------------------------------------------

    if remaining_hours <= 24:
        return 35

    # --------------------------------------------------------
    # DUE WITHIN 3 DAYS
    # --------------------------------------------------------

    if remaining_hours <= 72:
        return 25

    # --------------------------------------------------------
    # FUTURE DEADLINE
    # --------------------------------------------------------

    return 10


# ============================================================
# DURATION SCORE
# ============================================================

def calculate_duration_score(
    estimated_duration
):
    """
    Give a small scheduling advantage to
    shorter tasks because they can fit into
    smaller available windows.
    """

    if estimated_duration is None:
        return 0

    if estimated_duration <= 30:
        return 5

    if estimated_duration <= 60:
        return 3

    return 1


# ============================================================
# CALCULATE PRIORITY
# ============================================================

def calculate_priority(task):
    """
    Calculate a deterministic priority score.

    Factors:

    1. Importance
    2. Deadline urgency
    3. Estimated duration

    Completed tasks are not expected to reach
    this service because the planner filters them.
    """

    score = 0

    # ========================================================
    # 1. IMPORTANCE
    # ========================================================

    if task.importance is not None:

        importance = max(
            1,
            min(
                task.importance,
                5,
            ),
        )

        score += importance * 20

    # ========================================================
    # 2. DEADLINE
    # ========================================================

    score += calculate_deadline_score(
        task.deadline
    )

    # ========================================================
    # 3. DURATION
    # ========================================================

    score += calculate_duration_score(
        task.estimated_duration
    )

    # ========================================================
    # 4. PRIORITY LABEL
    # ========================================================

    label = get_priority_label(
        score
    )

    return {
        "task_id": task.id,
        "task_title": task.title,
        "score": score,
        "priority": label,
    }


# ============================================================
# PRIORITIZE ALL TASKS
# ============================================================

def prioritize_tasks(tasks):
    """
    Calculate priority for all tasks and
    return them from highest to lowest priority.

    When scores are equal:

    1. Earlier deadline comes first.
    2. Higher importance comes next.
    3. Shorter duration comes next.
    """

    prioritized = []

    for task in tasks:

        result = calculate_priority(
            task
        )

        prioritized.append(
            {
                **result,
                "_deadline": task.deadline,
                "_importance": (
                    task.importance or 0
                ),
                "_duration": (
                    task.estimated_duration
                    or 999999
                ),
            }
        )

    # --------------------------------------------------------
    # Sort intelligently
    # --------------------------------------------------------

    prioritized.sort(
        key=lambda task: (
            -task["score"],

            task["_deadline"]
            if task["_deadline"]
            is not None
            else datetime.max,

            -task["_importance"],

            task["_duration"],
        )
    )

    # --------------------------------------------------------
    # Remove internal sorting fields
    # --------------------------------------------------------

    for task in prioritized:

        task.pop(
            "_deadline",
            None
        )

        task.pop(
            "_importance",
            None
        )

        task.pop(
            "_duration",
            None
        )

    return prioritized