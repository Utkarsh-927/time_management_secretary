import os

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.database import Base, engine

from .services.background import start_reminder_worker

from .models.task import Task
from .models.meeting import Meeting
from .models.availability import Availability
from .models.reminder import Reminder

from .api.tasks import router as task_router
from .api.meetings import router as meetings_router
from .api.availability import router as availability_router
from .api.reminders import router as reminder_router
from .api.ai import router as ai_router
from .api.priority import router as priority_router
from .api.plan import router as plan_router
from .api.dashboard import router as dashboard_router
from .api.planner import router as planner_router


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# DATABASE TABLES
# ============================================================

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# FRONTEND URL
# ============================================================

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Management Model",
    description=(
        "AI-powered personal time "
        "management and scheduling system"
    ),
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

if FRONTEND_URL not in allowed_origins:
    allowed_origins.append(
        FRONTEND_URL
    )


app.add_middleware(
    CORSMiddleware,

    allow_origins=allowed_origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():
    start_reminder_worker()


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    task_router
)

app.include_router(
    meetings_router
)

app.include_router(
    availability_router
)

app.include_router(
    reminder_router
)

app.include_router(
    ai_router
)

app.include_router(
    priority_router
)

app.include_router(
    plan_router
)

app.include_router(
    dashboard_router
)

app.include_router(
    planner_router
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": (
            "Management Model API is running"
        )
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }