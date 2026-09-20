"""Date/time helpers.

Storage convention (important for consistent queries):

* Slot/appointment *calendar* fields are strings: ``date`` = ``"YYYY-MM-DD"``,
  ``start_time``/``end_time`` = ``"HH:MM"`` — clinic-local wall-clock time.
* Slots/appointments also store ``start_at``/``end_at`` as **naive UTC datetimes**
  (MongoDB's native behaviour) so range queries and expiry checks are timezone-safe.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Current time as a *naive* UTC datetime (what MongoDB stores)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def date_to_str(d: date) -> str:
    return d.isoformat()


def time_to_str(t: time) -> str:
    return t.strftime("%H:%M")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def local_to_utc(date_str: str, time_str: str, tz_name: str) -> datetime:
    """Clinic-local wall-clock -> naive UTC."""
    local = datetime.combine(parse_date(date_str), parse_time(time_str)).replace(tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def today_local(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def minutes_between(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def add_minutes(t: time, minutes: int) -> time:
    dt = datetime.combine(date(2000, 1, 1), t) + timedelta(minutes=minutes)
    return dt.time()
