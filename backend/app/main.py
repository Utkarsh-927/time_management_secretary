import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.init_db import init_database
from .services.background import start_reminder_worker
from .api.tasks import router as task_router
from .api.meetings import router as meetings_router
from .api.availability import router as availability_router
from .api.reminders import router as reminder_router
from .api.ai import router as ai_router
from .api.secretary import router as secretary_router
from .api.priority import router as priority_router
from .api.plan import router as plan_router
from .api.dashboard import router as dashboard_router
from .api.planner import router as planner_router

load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in FRONTEND_URL.split(",") if origin.strip()]
for origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
    if origin not in allowed_origins:
        allowed_origins.append(origin)

app = FastAPI(
    title="Management Model - AI Secretary",
    description="AI-powered personal secretary, memory, task and scheduling system",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_database()
    start_reminder_worker()

for router in [
    task_router, meetings_router, availability_router, reminder_router,
    ai_router, secretary_router, priority_router, plan_router,
    dashboard_router, planner_router,
]:
    app.include_router(router)

@app.get("/")
def root():
    return {"message": "Management Model AI Secretary API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
