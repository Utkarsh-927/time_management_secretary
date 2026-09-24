from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.task import Task
from ..schemas.task import TaskCreate, TaskResponse, TaskUpdate


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


@router.post("/", response_model=TaskResponse)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
):
    task = Task(
        user_id=task_data.user_id,
        title=task_data.title,
        description=task_data.description,
        deadline=task_data.deadline,
        estimated_duration=task_data.estimated_duration,
        remaining_duration=task_data.estimated_duration,
        progress_percent=0,
        importance=task_data.importance,
        urgency=3,
        priority_score=0.0,
        status="pending",
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.get("/", response_model=List[TaskResponse])
def get_tasks(
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .order_by(
            Task.deadline.asc().nullslast(),
            Task.id.asc(),
        )
        .all()
    )

    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        .first()
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
):
    user_id = task_data.user_id or "default"

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        .first()
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    update_data = task_data.model_dump(
        exclude_unset=True,
        exclude={"user_id"},
    )

    for key, value in update_data.items():
        setattr(task, key, value)

    if (
        "estimated_duration" in update_data
        and "remaining_duration" not in update_data
    ):
        task.remaining_duration = (
            update_data["estimated_duration"]
        )

    if task.status == "completed":
        task.progress_percent = 100
        task.remaining_duration = 0
        task.completed_at = (
            task.completed_at
            or datetime.utcnow()
        )

    db.commit()
    db.refresh(task)

    return task


@router.patch(
    "/{task_id}/complete",
    response_model=TaskResponse,
)
def complete_task(
    task_id: int,
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        .first()
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    task.status = "completed"
    task.progress_percent = 100
    task.remaining_duration = 0
    task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    user_id: str = Query(
        default="default",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        .first()
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    db.delete(task)
    db.commit()

    return {
        "message": "Task deleted successfully",
        "task_id": task_id,
    }