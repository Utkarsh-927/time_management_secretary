from datetime import date, datetime, timedelta, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.database import Base

from backend.app.models.task import Task
from backend.app.models.meeting import Meeting
from backend.app.models.reminder import Reminder

from backend.app.ai.commands import detect_command
from backend.app.ai.command_executor import execute_command


# ============================================================
# TEST DATABASE
# ============================================================

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def setup_database():
    Base.metadata.create_all(
        bind=engine
    )


def teardown_database():
    Base.metadata.drop_all(
        bind=engine
    )


# ============================================================
# TASK FIXTURE
# ============================================================

def create_task(
    db,
    title="Python",
    importance=3,
    deadline=None,
):
    task = Task(
        title=title,
        description="Test task",
        deadline=deadline,
        estimated_duration=60,
        importance=importance,
        status="pending",
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


# ============================================================
# MEETING FIXTURE
# ============================================================

def create_meeting(db):
    tomorrow = (
        date.today()
        + timedelta(days=1)
    )

    start_time = datetime.combine(
        tomorrow,
        time(15, 0),
    )

    end_time = datetime.combine(
        tomorrow,
        time(16, 0),
    )

    meeting = Meeting(
        title="Team Meeting",
        description="Test meeting",
        start_time=start_time,
        end_time=end_time,
        location="Online",
        participants="Test User",
    )

    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return meeting


# ============================================================
# TEST DB HELPERS
# ============================================================

def get_test_db():
    setup_database()

    return TestingSessionLocal()


def close_test_db(db):
    db.close()
    teardown_database()


# ============================================================
# UPDATE TASK IMPORTANCE
# ============================================================

def test_update_task_importance():

    db = get_test_db()

    try:
        task = create_task(
            db,
            title="Python",
            importance=3,
        )

        command = detect_command(
            "Make my Python task critical."
        )

        result = execute_command(
            db,
            command,
        )

        assert result["success"] is True

        db.refresh(task)

        task_importance = getattr(
            task,
            "importance",
            None,
        )

        assert task_importance == 5

    finally:
        close_test_db(db)


# ============================================================
# UPDATE TASK DEADLINE
# ============================================================

def test_update_task_deadline():

    db = get_test_db()

    try:
        task = create_task(
            db,
            title="Python",
        )

        command = detect_command(
            "Move my Python task to tomorrow."
        )

        result = execute_command(
            db,
            command,
        )

        assert result["success"] is True

        db.refresh(task)

        expected_date = (
            date.today()
            + timedelta(days=1)
        )

        task_deadline = getattr(
            task,
            "deadline",
            None,
        )

        assert task_deadline is not None
        assert task_deadline.date() == expected_date

    finally:
        close_test_db(db)


# ============================================================
# DELETE TASK
# ============================================================

def test_delete_task():

    db = get_test_db()

    try:
        task = create_task(
            db,
            title="Python",
        )

        task_id = getattr(
            task,
            "id",
            None,
        )

        command = detect_command(
            "Cancel my Python task."
        )

        result = execute_command(
            db,
            command,
        )

        assert result["success"] is True

        deleted_task = (
            db.query(Task)
            .filter(
                Task.id == task_id
            )
            .first()
        )

        assert deleted_task is None

    finally:
        close_test_db(db)


# ============================================================
# UPDATE MEETING
# ============================================================

def test_update_meeting():

    db = get_test_db()

    try:
        meeting = create_meeting(db)

        original_start = getattr(
            meeting,
            "start_time",
            None,
        )

        assert original_start is not None

        original_time = (
            original_start.time()
        )

        command = detect_command(
            "Move my team meeting to next Monday."
        )

        result = execute_command(
            db,
            command,
        )

        assert result["success"] is True

        db.refresh(meeting)

        updated_start = getattr(
            meeting,
            "start_time",
            None,
        )

        assert updated_start is not None

        assert (
            updated_start.weekday()
            == 0
        )

        assert (
            updated_start.time()
            == original_time
        )

    finally:
        close_test_db(db)


# ============================================================
# DELETE MEETING
# ============================================================

def test_delete_meeting():

    db = get_test_db()

    try:
        meeting = create_meeting(db)

        meeting_id = getattr(
            meeting,
            "id",
            None,
        )

        command = detect_command(
            "Cancel tomorrow's meeting."
        )

        result = execute_command(
            db,
            command,
        )

        assert result["success"] is True

        deleted_meeting = (
            db.query(Meeting)
            .filter(
                Meeting.id == meeting_id
            )
            .first()
        )

        assert deleted_meeting is None

    finally:
        close_test_db(db)


# ============================================================
# CREATE REMINDER
# ============================================================

def test_create_reminder():

    db = get_test_db()

    try:
        meeting = create_meeting(db)

        meeting_start = getattr(
            meeting,
            "start_time",
            None,
        )

        meeting_id = getattr(
            meeting,
            "id",
            None,
        )

        assert meeting_start is not None
        assert meeting_id is not None

        command = detect_command(
            "Remind me 30 minutes before my meeting."
        )

        result = execute_command(
            db,
            command,
        )

        assert result["success"] is True

        reminders = (
            db.query(Reminder)
            .all()
        )

        assert len(reminders) == 1

        reminder = reminders[0]

        expected_time = (
            meeting_start
            - timedelta(
                minutes=30
            )
        )

        reminder_time = getattr(
            reminder,
            "reminder_time",
            None,
        )

        reminder_related_id = getattr(
            reminder,
            "related_id",
            None,
        )

        reminder_type = getattr(
            reminder,
            "reminder_type",
            None,
        )

        reminder_status = getattr(
            reminder,
            "status",
            None,
        )

        assert reminder_time == expected_time

        assert (
            reminder_related_id
            == meeting_id
        )

        assert (
            reminder_type
            == "before_event"
        )

        assert (
            reminder_status
            == "pending"
        )

    finally:
        close_test_db(db)