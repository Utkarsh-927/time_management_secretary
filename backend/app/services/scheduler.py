from datetime import datetime, timedelta



SLOT_INTERVAL_MINUTES = 30



def daterange(start_date, end_date):
    """
    Generate every date from start_date to end_date.
    """

    current = start_date

    while current <= end_date:
        yield current
        current += timedelta(days=1)


def is_available_day(
    availability,
    current_date,
):
    """
    Check whether a date is allowed by the
    availability recurrence rules.
    """

    recurrence = (
        availability.recurrence
        or "none"
    )

    
    if recurrence == "none":
        return True

    
    if recurrence == "daily":
        return True

    
    if recurrence == "weekly":

        weekdays = (
            availability.weekdays
            or []
        )

        if isinstance(
            weekdays,
            str,
        ):

            weekdays = [
                day.strip()
                for day in weekdays.split(",")
                if day.strip()
            ]

        weekday_name = (
            current_date.strftime("%A")
        )

        return (
            weekday_name
            in weekdays
        )

    return False


def round_up_to_next_slot(
    value,
    minutes=SLOT_INTERVAL_MINUTES,
):
    """
    Round a datetime up to the next scheduling slot.

    Examples:

        10:07 -> 10:30
        10:30 -> 10:30
        10:31 -> 11:00
    """

    if value.second or value.microsecond:

        value = value.replace(
            second=0,
            microsecond=0,
        )

    remainder = (
        value.minute % minutes
    )

    if remainder == 0:
        return value

    return value + timedelta(
        minutes=(
            minutes - remainder
        )
    )


def normalize_deadline(deadline):
    """
    Normalize a task deadline into a datetime.
    """

    if deadline is None:
        return None

    if isinstance(
        deadline,
        datetime,
    ):
        return deadline

    if isinstance(
        deadline,
        str,
    ):

        try:
            return datetime.fromisoformat(
                deadline
            )

        except ValueError:
            return None

    return None


def overlaps(
    start_time,
    end_time,
    existing_start,
    existing_end,
):
    """
    Return True when two time ranges overlap.
    """

    return (
        start_time < existing_end
        and end_time > existing_start
    )



def generate_availability_windows(
    availability,
):
    """
    Convert an Availability database object into
    individual daily datetime windows.

    Supports:

    - none
    - daily
    - weekly
    """

    if availability.start_date is None:
        return []

    if availability.end_date is None:
        return []

    if availability.start_time is None:
        return []

    if availability.end_time is None:
        return []

    windows = []

    for current_date in daterange(
        availability.start_date,
        availability.end_date,
    ):

        if not is_available_day(
            availability,
            current_date,
        ):
            continue

        start_datetime = datetime.combine(
            current_date,
            availability.start_time,
        )

        end_datetime = datetime.combine(
            current_date,
            availability.end_time,
        )

        if (
            start_datetime
            >= end_datetime
        ):
            continue

        windows.append(
            {
                "start_time": start_datetime,
                "end_time": end_datetime,
            }
        )

    return windows



def has_meeting_conflict(
    start_time,
    end_time,
    meetings,
):
    """
    Check whether a proposed task slot overlaps
    any meeting.
    """

    for meeting in meetings:

        if meeting.start_time is None:
            continue

        if meeting.end_time is None:
            continue

        if overlaps(
            start_time,
            end_time,
            meeting.start_time,
            meeting.end_time,
        ):
            return True

    return False



def has_scheduled_task_conflict(
    start_time,
    end_time,
    scheduled_slots,
):
    """
    Check whether a proposed task slot overlaps
    an already scheduled task.
    """

    for scheduled in scheduled_slots:

        if overlaps(
            start_time,
            end_time,
            scheduled["start_time"],
            scheduled["end_time"],
        ):
            return True

    return False



def generate_time_slots(
    start_time,
    end_time,
    duration_minutes,
    meetings=None,
    scheduled_slots=None,
):
    """
    Generate all valid candidate task slots.

    Slots are aligned to 30-minute boundaries and
    avoid meetings and previously scheduled tasks.
    """

    if meetings is None:
        meetings = []

    if scheduled_slots is None:
        scheduled_slots = []

    if duration_minutes is None:
        return []

    if duration_minutes <= 0:
        return []

    duration = timedelta(
        minutes=duration_minutes
    )

    slots = []

    current = round_up_to_next_slot(
        start_time
    )

    while (
        current + duration
        <= end_time
    ):

        slot_end = (
            current + duration
        )

       
        if has_meeting_conflict(
            current,
            slot_end,
            meetings,
        ):

            current += timedelta(
                minutes=SLOT_INTERVAL_MINUTES
            )

            continue

        
        if has_scheduled_task_conflict(
            current,
            slot_end,
            scheduled_slots,
        ):

            current += timedelta(
                minutes=SLOT_INTERVAL_MINUTES
            )

            continue

        slots.append(
            {
                "start_time": current,
                "end_time": slot_end,
            }
        )

        current += timedelta(
            minutes=SLOT_INTERVAL_MINUTES
        )

    return slots



def score_candidate_slot(
    slot,
    window_start,
    window_end,
):
    """
    Score a candidate slot.

    Lower score = better slot.

    Scheduling policy:

    1. Earliest start time
    2. Smaller unused time

    Priority itself is NOT calculated here.

    Tasks are already supplied to the scheduler
    in priority order by the planner.
    """

    slot_start = slot["start_time"]
    slot_end = slot["end_time"]

    remaining_before = (
        slot_start - window_start
    )

    remaining_after = (
        window_end - slot_end
    )

    total_waste = (
        remaining_before.total_seconds()
        + remaining_after.total_seconds()
    )

    return (
        slot_start,
        total_waste,
    )



def find_best_slot(
    task,
    availability_list,
    meetings,
    scheduled_slots,
    now,
):
    """
    Search all valid availability windows.

    The earliest valid slot is preferred.

    This preserves planner priority ordering because
    tasks are processed in priority order.
    """

    if task.estimated_duration is None:
        return None

    if task.estimated_duration <= 0:
        return None

    deadline = normalize_deadline(
        task.deadline
    )

    candidates = []

    
    for availability in availability_list:

        windows = (
            generate_availability_windows(
                availability
            )
        )

        for window in windows:

            window_start = window[
                "start_time"
            ]

            window_end = window[
                "end_time"
            ]

            
            if window_end <= now:
                continue

            
            effective_start = (
                window_start
            )

            if effective_start < now:

                effective_start = (
                    round_up_to_next_slot(
                        now
                    )
                )

           
            effective_end = (
                window_end
            )

            if deadline is not None:

                # Window starts at/after deadline.
                if (
                    effective_start
                    >= deadline
                ):
                    continue

                # Task must finish by deadline.
                if deadline < effective_end:

                    effective_end = (
                        deadline
                    )

            
            if (
                effective_start
                >= effective_end
            ):
                continue

            
            slots = generate_time_slots(
                effective_start,
                effective_end,
                task.estimated_duration,
                meetings,
                scheduled_slots,
            )

            
            for slot in slots:

                if deadline is not None:

                    if (
                        slot["end_time"]
                        > deadline
                    ):
                        continue

                if (
                    slot["start_time"]
                    < now
                ):
                    continue

                score = score_candidate_slot(
                    slot,
                    effective_start,
                    effective_end,
                )

                candidates.append(
                    {
                        "slot": slot,
                        "score": score,
                    }
                )

   
    if not candidates:
        return None

   
    candidates.sort(
        key=lambda item: item["score"]
    )

    return candidates[0]["slot"]



def schedule_task(
    task,
    availability_list,
    meetings=None,
    scheduled_slots=None,
):
    """
    Schedule one task while respecting:

    - availability
    - recurrence
    - meetings
    - existing scheduled tasks
    - deadlines
    - current date/time
    """

    if meetings is None:
        meetings = []

    if scheduled_slots is None:
        scheduled_slots = []

    now = datetime.now()

    slot = find_best_slot(
        task=task,
        availability_list=availability_list,
        meetings=meetings,
        scheduled_slots=scheduled_slots,
        now=now,
    )

    if slot is None:
        return None

    return {
        "task_id": task.id,

        "task_title": task.title,

        "start_time": slot[
            "start_time"
        ],

        "end_time": slot[
            "end_time"
        ],

        "duration_minutes": (
            task.estimated_duration
        ),
    }



def schedule_tasks(
    tasks,
    availability_list,
    meetings=None,
):
    """
    Schedule multiple tasks.

    IMPORTANT:

    The tasks are expected to already be ordered
    by priority by the planner.

    Therefore:

        Task 1 gets first available valid slot.
        Task 2 gets next available valid slot.
        Task 3 gets next available valid slot.

    This guarantees that a lower-priority task
    cannot take a slot before a higher-priority task
    when both are schedulable.
    """

    if meetings is None:
        meetings = []

    schedule = []

   
    for task in tasks:

        result = schedule_task(
            task,
            availability_list,
            meetings,
            schedule,
        )

        if result is not None:

            schedule.append(
                result
            )

 
    schedule.sort(
        key=lambda item:
            item["start_time"]
    )

    return schedule