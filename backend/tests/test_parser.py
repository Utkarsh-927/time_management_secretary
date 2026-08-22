from backend.app.ai.parser import (
    duration_from_message,
    importance_from_message,
    deadline_from_message,
)


def test_two_hours_duration():
    assert (
        duration_from_message(
            "I need two hours to finish my ML assignment."
        )
        == 120
    )


def test_one_hour_duration():
    assert (
        duration_from_message(
            "I need one hour to study Python."
        )
        == 60
    )


def test_minutes_duration():
    assert (
        duration_from_message(
            "I need 45 minutes to finish this."
        )
        == 45
    )


def test_important_task():
    assert (
        importance_from_message(
            "This task is important."
        )
        == 4
    )


def test_high_priority_task():
    assert (
        importance_from_message(
            "This is a high priority task."
        )
        == 4
    )


def test_critical_task():
    assert (
        importance_from_message(
            "This task is critical."
        )
        == 5
    )


def test_low_priority_task():
    assert (
        importance_from_message(
            "This is a low priority task."
        )
        == 1
    )


def test_tomorrow_deadline():
    assert (
        deadline_from_message(
            "Finish my Python assignment tomorrow."
        )
        == "tomorrow"
    )


def test_tomorrow_morning_deadline():
    result = deadline_from_message(
        "Finish my AI assignment tomorrow morning."
    )

    assert result is not None
    assert "09:00 AM" in result


def test_next_friday_deadline():
    result = deadline_from_message(
        "Finish this project next Friday."
    )

    assert result is not None