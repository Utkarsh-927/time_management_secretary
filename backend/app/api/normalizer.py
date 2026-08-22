from datetime import datetime, date, time, timedelta
import dateparser


def parse_date(value):
    """Convert natural-language date into Python date."""

    if value is None:
        return None

    if isinstance(value, date):
        return value

    text = str(value).strip().lower()

    # Handle relative dates explicitly
    if text == "today":
        return date.today()

    if text == "tomorrow":
        return date.today() + timedelta(days=1)

    if text == "yesterday":
        return date.today() - timedelta(days=1)

    parsed = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future"
        }
    )

    if parsed is None:
        raise ValueError(f"Could not parse date: {value}")

    return parsed.date()


def parse_time(value):
    """Convert natural-language time into Python time."""

    if value is None:
        return None

    if isinstance(value, time):
        return value

    text = str(value).strip()

    parsed = dateparser.parse(text)

    if parsed is None:
        raise ValueError(f"Could not parse time: {value}")

    return parsed.time()


def normalize_availability(data):
    """Convert AI availability output into DB-compatible values."""

    result = dict(data)

    result["start_date"] = parse_date(
        result.get("start_date")
    )

    result["end_date"] = parse_date(
        result.get("end_date")
    )

    result["start_time"] = parse_time(
        result.get("start_time")
    )

    result["end_time"] = parse_time(
        result.get("end_time")
    )

    # Don't store fake AI values such as ["unspecified"]
    if result.get("weekdays") == ["unspecified"]:
        result["weekdays"] = None

    return result


def normalize_meeting(data):
    """Convert AI meeting output into DB-compatible values."""

    result = dict(data)

    result["start_time"] = parse_datetime(
        result.get("start_time")
    )

    result["end_time"] = parse_datetime(
        result.get("end_time")
    )

    return result


def parse_datetime(value):
    """Convert natural-language datetime into Python datetime."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    parsed = dateparser.parse(
        str(value),
        settings={
            "PREFER_DATES_FROM": "future"
        }
    )

    if parsed is None:
        raise ValueError(
            f"Could not parse datetime: {value}"
        )

    return parsed