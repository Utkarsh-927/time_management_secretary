
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.task import Task
from ..services.priority import (
    calculate_priority,
    get_priority_label,
)


router = APIRouter(
    prefix="/priority",
    tags=["Priority"]
)


@router.get("/tasks")
def get_prioritized_tasks(
    db: Session = Depends(get_db)
):
    """
    Get all tasks sorted by calculated priority.
    """

    tasks = db.query(Task).all()

    prioritized_tasks = []

    for task in tasks:

        score = calculate_priority(
            importance=task.importance,
            deadline=task.deadline,
        )

        label = get_priority_label(score)

        prioritized_tasks.append(
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "deadline": task.deadline,
                "estimated_duration": task.estimated_duration,
                "importance": task.importance,
                "priority_score": score,
                "priority": label,
            }
        )

    # Highest priority first
    prioritized_tasks.sort(
        key=lambda task: task["priority_score"],
        reverse=True,
    )

    return {
        "count": len(prioritized_tasks),
        "tasks": prioritized_tasks,
    }

