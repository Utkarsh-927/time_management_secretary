"""Backward-compatible import wrapper. Use app.database.database for new code."""
from .database import Base, DATABASE_URL, SessionLocal, engine, get_db
__all__ = ["Base", "DATABASE_URL", "SessionLocal", "engine", "get_db"]
