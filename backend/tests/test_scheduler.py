from datetime import date, datetime, time

from types import SimpleNamespace

from backend.app.services.scheduler import (
    generate_availability_windows,
    generate_time_slots,
    is_available_day,
)


def make_availability(
    start_date,
    end_date,
    start_time,
    end_time,
    recurrence="none",
    weekdays=None,
):
    return SimpleNamespace(
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        recurrence=recurrence,
        weekdays=weekdays,
    )


def make_meeting(
    start_time,
    end_time,
):
    return SimpleNamespace(
        start_time=start_time,
        end_time=end_time,
    )


def test_non_recurring_availability():
    availability = make_availability(
        date(2026, 8, 21),
        date(2026, 8, 21),
        time(17, 0),
        time(21, 0),
    )

    windows = generate_availability_windows(
        availability
    )

    assert len(windows) == 1
    assert windows[0]["start_time"] == datetime(
        2026, 8, 21, 17, 0
    )
    assert windows[0]["end_time"] == datetime(
        2026, 8, 21, 21, 0
    )


def test_weekly_availability_respects_weekdays():
    availability = make_availability(
        date(2026, 8, 20),
        date(2026, 9, 19),
        time(18, 0),
        time(21, 0),
        recurrence="weekly",
        weekdays="Monday,Wednesday,Friday",
    )

    friday = date(2026, 8, 21)
    saturday = date(2026, 8, 22)

    assert is_available_day(
        availability,
        friday,
    ) is True

    assert is_available_day(
        availability,
        saturday,
    ) is False


def test_weekly_availability_generates_only_allowed_days():
    availability = make_availability(
        date(2026, 8, 20),
        date(2026, 8, 23),
        time(18, 0),
        time(21, 0),
        recurrence="weekly",
        weekdays="Friday",
    )

    windows = generate_availability_windows(
        availability
    )

    assert len(windows) == 1

    assert windows[0]["start_time"] == datetime(
        2026, 8, 22 - 1,
        18,
        0,
    )


def test_generate_time_slot_without_conflict():
    start = datetime(
        2026, 8, 21, 18, 0
    )

    end = datetime(
        2026, 8, 21, 21, 0
    )

    slots = generate_time_slots(
        start,
        end,
        60,
        meetings=[],
        scheduled_slots=[],
    )

    assert len(slots) > 0

    assert slots[0]["start_time"] == start

    assert (
        slots[0]["end_time"]
        == datetime(2026, 8, 21, 19, 0)
    )


def test_meeting_conflict_is_respected():
    start = datetime(
        2026, 8, 21, 18, 0
    )

    end = datetime(
        2026, 8, 21, 21, 0
    )

    meeting = make_meeting(
        datetime(2026, 8, 21, 18, 30),
        datetime(2026, 8, 21, 19, 30),
    )

    slots = generate_time_slots(
        start,
        end,
        60,
        meetings=[meeting],
        scheduled_slots=[],
    )

    for slot in slots:
        assert not (
            slot["start_time"]
            < meeting.end_time
            and slot["end_time"]
            > meeting.start_time
        )


def test_scheduled_task_conflict_is_respected():
    start = datetime(
        2026, 8, 21, 18, 0
    )

    end = datetime(
        2026, 8, 21, 21, 0
    )

    scheduled = [
        {
            "start_time": datetime(
                2026, 8, 21, 18, 0
            ),
            "end_time": datetime(
                2026, 8, 21, 19, 0
            ),
        }
    ]

    slots = generate_time_slots(
        start,
        end,
        60,
        meetings=[],
        scheduled_slots=scheduled,
    )

    for slot in slots:
        assert not (
            slot["start_time"]
            < scheduled[0]["end_time"]
            and slot["end_time"]
            > scheduled[0]["start_time"]
        )


def test_invalid_duration_returns_no_slots():
    start = datetime(
        2026, 8, 21, 18, 0
    )

    end = datetime(
        2026, 8, 21, 21, 0
    )

    assert (
        generate_time_slots(
            start,
            end,
            0,
            meetings=[],
            scheduled_slots=[],
        )
        == []
    )

    assert (
        generate_time_slots(
            start,
            end,
            None,
            meetings=[],
            scheduled_slots=[],
        )
        == []
    )


