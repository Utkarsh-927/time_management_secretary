from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..models.task import Task
from ..models.availability import Availability
from ..models.meeting import Meeting
from ..services.planner import create_plan



router = APIRouter(
    prefix="/planner",
    tags=["Planner"]
)



def availability_applies_to_date(
    availability,
    planning_date
):
    """
    Check whether an availability record applies
    to the requested planning date.
    """

    if availability.start_date is None:
        return False

    if availability.end_date is None:
        return False

    if not (
        availability.start_date
        <= planning_date
        <= availability.end_date
    ):
        return False

    recurrence = (
        availability.recurrence
        or "none"
    )

    
    if recurrence == "none":
        return True

    
    if recurrence == "daily":
        return True

    
    if recurrence == "weekly":

        weekdays = (
            availability.weekdays
            or ""
        )

        if isinstance(
            weekdays,
            str
        ):
            weekdays = [
                day.strip()
                for day in weekdays.split(",")
                if day.strip()
            ]

        weekday_name = (
            planning_date.strftime("%A")
        )

        return (
            weekday_name
            in weekdays
        )

    return False



@router.get("/")
def generate_plan(
    planning_date: date | None = Query(
        default=None,
        description=(
            "Date for which the plan should "
            "be generated. Defaults to today."
        )
    ),
    db: Session = Depends(get_db)
):
    """
    Generate a date-aware smart plan.

    Examples:

        GET /planner/

        GET /planner/?planning_date=2026-08-21
    """

   
    if planning_date is None:
        planning_date = date.today()

    
    start_of_day = datetime.combine(
        planning_date,
        time.min
    )

    end_of_day = datetime.combine(
        planning_date,
        time.max
    )

   
    tasks = (
        db.query(Task)
        .filter(
            Task.status != "completed"
        )
        .all()
    )

   
    all_availability = (
        db.query(Availability)
        .order_by(
            Availability.start_date
        )
        .all()
    )

    availability = [
        item
        for item in all_availability
        if availability_applies_to_date(
            item,
            planning_date
        )
    ]

    
    meetings = (
        db.query(Meeting)
        .filter(
            Meeting.start_time <= end_of_day,
            Meeting.end_time >= start_of_day
        )
        .order_by(
            Meeting.start_time
        )
        .all()
    )

    
    plan = create_plan(
        tasks,
        availability,
        meetings
    )

   
    return {
        "planning_date": (
            planning_date.isoformat()
        ),

        **plan
    }