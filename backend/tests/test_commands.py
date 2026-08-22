from backend.app.ai.commands import (
    detect_command,
)


def test_move_task_to_friday():
    result = detect_command(
        "Move my ML assignment to Friday."
    )

    assert result["intent"] == "update_task"
    assert result["task_title"] == "ML assignment"
    assert (
        result["changes"]["deadline_phrase"]
        == "Friday"
    )


def test_move_task_to_next_monday():
    result = detect_command(
        "Move my ML assignment to next Monday."
    )

    assert result["intent"] == "update_task"
    assert result["task_title"] == "ML assignment"
    assert (
        result["changes"]["deadline_phrase"]
        == "next Monday"
    )


def test_delete_task():
    result = detect_command(
        "Cancel my Python task."
    )

    assert result["intent"] == "delete_task"
    assert result["task_title"] == "Python"


def test_high_priority_task():
    result = detect_command(
        "Make Python task high priority."
    )

    assert result["intent"] == "update_task"
    assert result["task_title"] == "Python"
    assert result["changes"]["importance"] == 4


def test_critical_priority_task():
    result = detect_command(
        "Make my Python task critical."
    )

    assert result["intent"] == "update_task"
    assert result["task_title"] == "Python"
    assert result["changes"]["importance"] == 5


def test_low_priority_task():
    result = detect_command(
        "Set Python task to low priority."
    )

    assert result["intent"] == "update_task"
    assert result["task_title"] == "Python"
    assert result["changes"]["importance"] == 1


def test_delete_meeting():
    result = detect_command(
        "Cancel tomorrow's meeting."
    )

    assert result["intent"] == "delete_meeting"
    assert result["meeting_title"] == "Meeting"


def test_move_meeting():
    result = detect_command(
        "Move my team meeting to Friday."
    )

    assert result["intent"] == "update_meeting"
    assert result["meeting_title"] == "team"
    assert (
        result["changes"]["date_phrase"]
        == "Friday"
    )


def test_create_hour_reminder():
    result = detect_command(
        "Remind me 1 hour before the meeting."
    )

    assert result["intent"] == "create_reminder"
    assert result["minutes_before"] == 60
    assert result["target"] == "meeting"


def test_create_minute_reminder():
    result = detect_command(
        "Remind me 30 minutes before my meeting."
    )

    assert result["intent"] == "create_reminder"
    assert result["minutes_before"] == 30
    assert result["target"] == "meeting"


def test_normal_creation_message_is_not_command():
    result = detect_command(
        "I need an ML assignment tomorrow."
    )

    assert result["intent"] == "none"