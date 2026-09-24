from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    estimated_duration: Optional[int] = None
    importance: int = 3
    user_id: str = "default"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    estimated_duration: Optional[int] = None
    remaining_duration: Optional[int] = None
    progress_percent: Optional[int] = None
    importance: Optional[int] = None
    urgency: Optional[int] = None
    priority_score: Optional[float] = None
    status: Optional[str] = None
    user_id: Optional[str] = None


class TaskResponse(TaskCreate):
    id: int
    remaining_duration: Optional[int] = None
    progress_percent: int
    urgency: int
    priority_score: float
    status: str
    project_entity_id: Optional[int] = None
    assignee_entity_id: Optional[int] = None
    source_note_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)