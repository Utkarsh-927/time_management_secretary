
from ..services.priority import prioritize_tasks
from ..services.scheduler import schedule_tasks


def create_plan(tasks, availability, meetings):
    """
    Create a complete time-management plan.

    Steps:
    1. Prioritize tasks
    2. Schedule tasks according to priority
    3. Avoid meeting conflicts
    4. Report tasks that could not be scheduled
    """

    # ========================================================
    # 1. PRIORITIZE TASKS
    # ========================================================

    prioritized = prioritize_tasks(
        tasks
    )

    # Create a lookup so we can get the
    # original SQLAlchemy task objects.
    task_lookup = {
        task.id: task
        for task in tasks
    }

    # Highest priority first
    ordered_tasks = []

    for item in prioritized:

        task = task_lookup.get(
            item["task_id"]
        )

        if task is not None:
            ordered_tasks.append(
                task
            )

    # ========================================================
    # 2. SCHEDULE TASKS
    # ========================================================

    schedule = schedule_tasks(
        ordered_tasks,
        availability,
        meetings
    )

    # ========================================================
    # 3. ADD PRIORITY INFORMATION
    # ========================================================

    priority_lookup = {
        item["task_id"]: item
        for item in prioritized
    }

    for item in schedule:

        priority = priority_lookup.get(
            item["task_id"]
        )

        if priority:

            item["priority"] = (
                priority["priority"]
            )

            item["priority_score"] = (
                priority["score"]
            )

    # ========================================================
    # 4. FIND UNSCHEDULED TASKS
    # ========================================================

    scheduled_task_ids = {
        item["task_id"]
        for item in schedule
    }

    unscheduled_tasks = []

    for item in prioritized:

        task_id = item["task_id"]

        if task_id in scheduled_task_ids:
            continue

        task = task_lookup.get(
            task_id
        )

        if task is None:
            continue

        # ----------------------------------------------------
        # Determine a useful reason
        # ----------------------------------------------------

        reason = (
            "No available time slot "
            "before the task deadline."
        )

        if task.deadline is None:

            reason = (
                "No valid available time slot "
                "was found."
            )

        elif task.estimated_duration is None:

            reason = (
                "Task has no estimated duration."
            )

        elif task.estimated_duration <= 0:

            reason = (
                "Task has an invalid duration."
            )

        elif not availability:

            reason = (
                "No availability has been defined."
            )

        unscheduled_tasks.append(
            {
                "task_id": task.id,
                "task_title": task.title,
                "priority": item["priority"],
                "priority_score": item["score"],
                "reason": reason,
            }
        )

    # ========================================================
    # 5. RETURN COMPLETE PLAN
    # ========================================================

    return {
        "prioritized_tasks": prioritized,

        "schedule": schedule,

        "unscheduled_tasks": (
            unscheduled_tasks
        ),
    }

