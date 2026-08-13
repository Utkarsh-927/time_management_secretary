from fastapi import FastAPI

from .database.database import Base, engine

from .models.task import Task
from .models.meeting import Meeting
from .models.availability import Availability
from .models.reminder import Reminder

from .api.tasks import router as task_router
from .api.meetings import router as meeting_router
from .api.availability import router as availability_router
from .api.reminders import router as reminder_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Management Model",
    description="AI-powered personal time management and scheduling system",
    version="0.1.0"
)


app.include_router(task_router)
app.include_router(meeting_router)
app.include_router(availability_router)
app.include_router(reminder_router)


@app.get("/")
def root():
    return {
        "message": "Management Model API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }