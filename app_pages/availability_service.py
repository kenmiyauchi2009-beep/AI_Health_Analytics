"""Doctor availability (working hours, slot length, breaks, blocked periods) and bookable-slot generation.

One availability document per doctor. Weekly intervals and blocked periods are
in the doctor's own timezone; generated slots are returned as naive UTC
datetimes, the same convention pymongo uses for stored datetimes.

Functions take the MongoDB collection as an argument so they can be unit tested
without a live database.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOT_DURATIONS = [15, 30, 45, 60]
MAX_BREAK_MINUTES = 120
DEFAULT_TIMEZONE = "UTC"
BOOKING_WINDOW_DAYS = 30


def _normalize_email(value) -> str:
    return str(value or "").strip().lower()


def timezone_options() -> list[str]:
    return sorted(available_timezones())


def default_availability(doctor_email: str = "") -> dict:
    return {
        "doctor_email": _normalize_email(doctor_email),
        "timezone": DEFAULT_TIMEZONE,
        "slot_minutes": 30,
        "break_minutes": 0,
        "weekly": {str(day): [] for day in range(7)},
        "blocked": [],
    }


def parse_time(value) -> time:
    """Accept a ``time`` or an ``HH:MM`` string."""
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    return datetime.strptime(str(value).strip(), "%H:%M").time()


def parse_local_datetime(value) -> datetime:
    """Accept a naive ``datetime`` or a ``YYYY-MM-DDTHH:MM`` string (doctor's local time)."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, second=0, microsecond=0)
    return datetime.strptime(str(value).strip(), "%Y-%m-%dT%H:%M")


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def validate_availability(availability: dict) -> list[str]:
    """Return every problem with the settings; an empty list means they can be saved."""
    errors = []
    try:
        ZoneInfo(str(availability.get("timezone") or ""))
    except (ZoneInfoNotFoundError, ValueError):
        errors.append("Choose a valid timezone.")

    slot_minutes = availability.get("slot_minutes")
    if slot_minutes not in SLOT_DURATIONS:
        errors.append(f"Appointment duration must be one of {', '.join(map(str, SLOT_DURATIONS))} minutes.")
        slot_minutes = None
    break_minutes = availability.get("break_minutes")
    if not isinstance(break_minutes, int) or not 0 <= break_minutes <= MAX_BREAK_MINUTES:
        errors.append(f"Break between appointments must be 0-{MAX_BREAK_MINUTES} minutes.")

    weekly = availability.get("weekly") or {}
    for day, name in enumerate(WEEKDAYS):
        intervals = []
        for interval in weekly.get(str(day)) or []:
            try:
                start, end = parse_time(interval.get("start")), parse_time(interval.get("end"))
            except (TypeError, ValueError):
                errors.append(f"{name}: times must be HH:MM.")
                continue
            if start >= end:
                errors.append(f"{name}: start time {start:%H:%M} must be before end time {end:%H:%M}.")
                continue
            if slot_minutes and _minutes(end) - _minutes(start) < slot_minutes:
                errors.append(f"{name}: {start:%H:%M}-{end:%H:%M} is shorter than one {slot_minutes}-minute appointment.")
            intervals.append((start, end))
        intervals.sort()
        for (_, previous_end), (start, end) in zip(intervals, intervals[1:]):
            if start < previous_end:
                errors.append(f"{name}: {start:%H:%M}-{end:%H:%M} overlaps another interval.")

    for block in availability.get("blocked") or []:
        try:
            start, end = parse_local_datetime(block.get("start")), parse_local_datetime(block.get("end"))
        except (TypeError, ValueError):
            errors.append("Blocked periods need a valid start and end.")
            continue
        if start >= end:
            errors.append(f"Blocked period starting {start:%Y-%m-%d %H:%M} must end after it starts.")
    return errors


def _clean(availability: dict) -> dict:
    """Normalize to the stored shape: sorted HH:MM intervals and ISO blocked periods."""
    weekly = {}
    for day in range(7):
        intervals = sorted(
            (parse_time(interval["start"]), parse_time(interval["end"]))
            for interval in (availability.get("weekly") or {}).get(str(day)) or []
        )
        weekly[str(day)] = [{"start": f"{start:%H:%M}", "end": f"{end:%H:%M}"} for start, end in intervals]
    blocked = sorted(
        (
            {
                "start": f"{parse_local_datetime(block['start']):%Y-%m-%dT%H:%M}",
                "end": f"{parse_local_datetime(block['end']):%Y-%m-%dT%H:%M}",
                "reason": str(block.get("reason") or "").strip(),
            }
            for block in availability.get("blocked") or []
        ),
        key=lambda block: block["start"],
    )
    return {
        "timezone": availability["timezone"],
        "slot_minutes": availability["slot_minutes"],
        "break_minutes": availability["break_minutes"],
        "weekly": weekly,
        "blocked": blocked,
    }


def get_availability(availability_collection, doctor_email: str) -> dict | None:
    doctor_email = _normalize_email(doctor_email)
    if availability_collection is None or not doctor_email:
        return None
    return availability_collection.find_one({"doctor_email": doctor_email})


def save_availability(availability_collection, doctor_user: dict, availability: dict) -> list[str]:
    """Validate and store the signed-in doctor's own availability."""
    if availability_collection is None:
        return ["The database is not available right now."]
    doctor_email = _normalize_email((doctor_user or {}).get("email"))
    if not doctor_email:
        return ["You must be signed in as a doctor."]
    errors = validate_availability(availability)
    if errors:
        return errors

    fields = {**_clean(availability), "doctor_id": doctor_user.get("_id"), "updated_at": datetime.utcnow()}
    if availability_collection.find_one({"doctor_email": doctor_email}) is None:
        availability_collection.insert_one({"doctor_email": doctor_email, **fields})
    else:
        availability_collection.update_one({"doctor_email": doctor_email}, {"$set": fields})
    return []


def to_utc(local: datetime, tz_name: str) -> datetime:
    """Doctor-local naive datetime -> naive UTC."""
    return local.replace(tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc).replace(tzinfo=None)


def to_local(utc: datetime, tz_name: str) -> datetime:
    """Naive UTC datetime -> doctor-local aware datetime."""
    return utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))


def local_today(availability: dict, now: datetime) -> date:
    return to_local(now, availability["timezone"]).date()


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def generate_slots(
    availability: dict,
    local_date: date,
    now: datetime,
    busy: list[tuple[datetime, datetime]] = (),
) -> list[tuple[datetime, datetime]]:
    """Bookable (start, end) slots in naive UTC for one doctor-local date.

    Slots are laid out from the start of each interval, one appointment plus the
    break apart, and must end within the interval. Past slots, blocked periods
    and ``busy`` (naive UTC reservations) are removed.
    """
    tz_name = availability["timezone"]
    duration = timedelta(minutes=availability["slot_minutes"])
    step = duration + timedelta(minutes=availability.get("break_minutes") or 0)
    blocked = [
        (parse_local_datetime(block["start"]), parse_local_datetime(block["end"]))
        for block in availability.get("blocked") or []
    ]

    slots = []
    for interval in (availability.get("weekly") or {}).get(str(local_date.weekday())) or []:
        cursor = datetime.combine(local_date, parse_time(interval["start"]))
        interval_end = datetime.combine(local_date, parse_time(interval["end"]))
        while cursor + duration <= interval_end:
            slot_end = cursor + duration
            start_utc, end_utc = to_utc(cursor, tz_name), to_utc(slot_end, tz_name)
            if (
                start_utc > now
                and not any(_overlaps(cursor, slot_end, start, end) for start, end in blocked)
                and not any(_overlaps(start_utc, end_utc, start, end) for start, end in busy)
            ):
                slots.append((start_utc, end_utc))
            cursor += step
    return slots


def available_dates(
    availability: dict,
    now: datetime,
    busy: list[tuple[datetime, datetime]] = (),
    days: int = BOOKING_WINDOW_DAYS,
) -> list[date]:
    """Doctor-local dates in the booking window that still have at least one free slot."""
    today = local_today(availability, now)
    return [
        today + timedelta(days=offset)
        for offset in range(days)
        if generate_slots(availability, today + timedelta(days=offset), now, busy)
    ]
