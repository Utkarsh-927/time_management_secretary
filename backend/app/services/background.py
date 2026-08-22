import time
import threading

from ..database.database import SessionLocal
from .reminder_worker import check_due_reminders


def reminder_loop():
    """
    Continuously check for due reminders.
    """

    while True:

        db = SessionLocal()

        try:
            check_due_reminders(db)

        except Exception as error:
            print(
                f"Reminder worker error: {error}"
            )

        finally:
            db.close()

        # Check every 30 seconds
        time.sleep(30)


def start_reminder_worker():
    """
    Start the reminder worker in a background thread.
    """

    thread = threading.Thread(
        target=reminder_loop,
        daemon=True
    )

    thread.start()

    print(
        "Reminder background worker started."
    )