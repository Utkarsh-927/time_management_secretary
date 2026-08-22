
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.task import Task
from ..models.availability import Availability
from ..models.meeting import Meeting
from ..services.planner import create_plan


router = APIRouter(
    prefix="/plan",
    tags=["Planning"]
)


@router.get("")
def get_plan(
    db: Session = Depends(get_db)
):
    """
    Generate a complete time-management plan
    using the current database data.
    """

    # Get data from database
    tasks = db.query(Task).all()
    availability = db.query(Availability).all()
    meetings = db.query(Meeting).all()

    # Generate plan
    result = create_plan(
        tasks,
        availability,
        meetings
    )

    return {
        "message": "Plan generated successfully",
        "data": result
    }

