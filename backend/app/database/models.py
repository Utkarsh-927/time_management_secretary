"""Backward-compatible aliases for legacy service imports."""
from ..models import Task as TaskDB, Meeting as MeetingDB, Availability as AvailabilityDB, Reminder as ReminderDB
__all__ = ["TaskDB", "MeetingDB", "AvailabilityDB", "ReminderDB"]
