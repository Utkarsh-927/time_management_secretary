
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.reminder import Reminder
from .notification import send_notification


def check_due_reminders(db: Session):
    """
    Find all pending reminders whose reminder_time
    has arrived, send a notification, and mark them
    as sent.
    """

    now = datetime.now()

    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.status == "pending",
            Reminder.reminder_time <= now
        )
        .all()
    )

    triggered = []

    for reminder in reminders:

       
        send_notification(
            title=reminder.title,
            message=reminder.message
        )

       
        reminder.status = "sent"

        triggered.append({
            "id": reminder.id,
            "title": reminder.title,
            "message": reminder.message,
            "reminder_time": reminder.reminder_time,
            "status": "sent"
        })

    
    if triggered:
        db.commit()

    return triggered

