"""Timezone-aware natural language date/time parsing for Pavi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re

import dateparser

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

RELATIVE_IN = re.compile(
    r"\b(?:in|after)\s+(\d+)\s+(minutes?|hours?|days?|weeks?)\b",
    re.IGNORECASE,
)
OFFSET_BEFORE = re.compile(
    r"\b(\d+)\s+(minutes?|hours?)\s+before\b",
    re.IGNORECASE,
)
EVERY_DAY = re.compile(r"\bevery\s+day\b", re.IGNORECASE)
EVERY_WEEKDAY = re.compile(
    r"\bevery\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
DAY_AFTER_TOMORROW = re.compile(r"\b(day after tomorrow|parso)\b", re.IGNORECASE)
TONIGHT = re.compile(r"\b(tonight|this evening|aaj shaam)\b", re.IGNORECASE)
TOMORROW_MORNING = re.compile(r"\b(tomorrow morning|kal subah)\b", re.IGNORECASE)
NOON = re.compile(r"\b(noon|midday)\b", re.IGNORECASE)
INDIAN_TODAY = re.compile(r"\b(aaj)\b", re.IGNORECASE)
INDIAN_TOMORROW = re.compile(r"\b(kal)\b", re.IGNORECASE)
CLOCK_TOKEN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje|o'?clock)?\b",
    re.IGNORECASE,
)


@dataclass
class ParsedDateTime:
    dt_utc: datetime
    timezone: str
    local_dt: datetime
    recurrence_rule: str | None = None
    offset_minutes: int | None = None
    ambiguous: bool = False
    source: str = ""


def get_zone(name: str | None, default: str = "Asia/Kolkata") -> ZoneInfo:
    try:
        return ZoneInfo(name or default)
    except ZoneInfoNotFoundError:
        return ZoneInfo(default)


def ensure_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def from_utc(dt: datetime, tz_name: str) -> datetime:
    return to_utc(dt).astimezone(get_zone(tz_name))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def format_local(dt: datetime, tz_name: str, *, with_date: bool = True) -> str:
    local = from_utc(dt, tz_name)
    if with_date:
        return local.strftime("%A, %d %b %Y at %I:%M %p IST").replace(" 0", " ")
    return local.strftime("%I:%M %p IST").lstrip("0")


def _apply_time_hints(text: str, local_now: datetime) -> datetime | None:
    zone = local_now.tzinfo
    lower = text.lower().strip()

    m = RELATIVE_IN.search(lower)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        delta = {
            "minute": timedelta(minutes=amount),
            "minutes": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "hours": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "days": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "weeks": timedelta(weeks=amount),
        }[unit]
        return local_now + delta

    if DAY_AFTER_TOMORROW.search(lower):
        base = (local_now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
        return _merge_clock(lower, base)

    if TOMORROW_MORNING.search(lower):
        return (local_now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    if TONIGHT.search(lower):
        base = local_now.replace(hour=21, minute=0, second=0, microsecond=0)
        if base <= local_now:
            base += timedelta(days=1)
        return _merge_clock(lower, base)

    if NOON.search(lower) and ("tomorrow" in lower or INDIAN_TOMORROW.search(lower)):
        return (local_now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    if NOON.search(lower):
        base = local_now.replace(hour=12, minute=0, second=0, microsecond=0)
        if base <= local_now:
            base += timedelta(days=1)
        return base

    if EVERY_DAY.search(lower) or EVERY_WEEKDAY.search(lower):
        base = local_now.replace(second=0, microsecond=0)
        merged = _merge_clock(lower, base)
        if merged <= local_now:
            merged += timedelta(days=1)
        return merged

    if "tomorrow" in lower or INDIAN_TOMORROW.search(lower):
        base = (local_now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return _merge_clock(lower, base)

    if "today" in lower or INDIAN_TODAY.search(lower):
        base = local_now.replace(second=0, microsecond=0)
        return _merge_clock(lower, base)

    for name, idx in WEEKDAYS.items():
        if re.search(rf"\bnext\s+{name}\b", lower):
            days_ahead = (idx - local_now.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            base = (local_now + timedelta(days=days_ahead)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            return _merge_clock(lower, base)

    if re.search(r"\b(shaam|evening)\b", lower) and CLOCK_TOKEN.search(lower):
        base = local_now.replace(second=0, microsecond=0)
        merged = _merge_clock(lower, base)
        if merged <= local_now:
            merged += timedelta(days=1)
        return merged

    if CLOCK_TOKEN.search(lower):
        base = local_now.replace(second=0, microsecond=0)
        merged = _merge_clock(lower, base)
        if merged <= local_now:
            merged += timedelta(days=1)
        return merged
    return None


def _merge_clock(text: str, base: datetime) -> datetime:
    clock = CLOCK_TOKEN.search(text)
    if not clock:
        return base
    hour = int(clock.group(1))
    minute = int(clock.group(2) or 0)
    ampm = (clock.group(3) or "").lower()
    if ampm in {"baje", "oclock", "o'clock"}:
        ampm = ""
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif not ampm:
        # Indian appointment habit: 1–6 without am/pm usually means evening.
        if 1 <= hour <= 6:
            hour += 12
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def extract_offset_minutes(text: str) -> int | None:
    m = OFFSET_BEFORE.search(text or "")
    if not m:
        if re.search(r"\bone hour before\b", text or "", re.I):
            return 60
        if re.search(r"\bhalf an hour before\b", text or "", re.I):
            return 30
        return None
    amount = int(m.group(1))
    unit = m.group(2).lower()
    return amount * 60 if unit.startswith("hour") else amount


def extract_recurrence(text: str) -> str | None:
    if EVERY_DAY.search(text or ""):
        return "FREQ=DAILY"
    m = EVERY_WEEKDAY.search(text or "")
    if m:
        day = m.group(1)[:2].upper()
        return f"FREQ=WEEKLY;BYDAY={day}"
    return None


def parse_natural_datetime(
    text: str,
    *,
    timezone_name: str = "Asia/Kolkata",
    now: datetime | None = None,
) -> ParsedDateTime | None:
    if not (text or "").strip():
        return None
    zone = get_zone(timezone_name)
    local_now = (now or now_utc()).astimezone(zone)
    recurrence = extract_recurrence(text)
    offset = extract_offset_minutes(text)

    hinted = _apply_time_hints(text, local_now)
    parsed: datetime | None = hinted

    if parsed is None:
        settings = {
            "TIMEZONE": timezone_name,
            "TO_TIMEZONE": timezone_name,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "DATE_ORDER": "DMY",
            "RELATIVE_BASE": local_now.replace(tzinfo=None),
        }
        candidate = dateparser.parse(text, settings=settings)
        if candidate is not None:
            parsed = ensure_aware(candidate, zone)

    if parsed is None:
        return None

    parsed = ensure_aware(parsed, zone)
    if parsed <= local_now and not recurrence:
        # If the clock time already passed today, push to tomorrow.
        if parsed.date() == local_now.date():
            parsed = parsed + timedelta(days=1)
        elif parsed <= local_now:
            parsed = parsed + timedelta(days=1)

    ambiguous = not bool(
        re.search(r"\b(\d{1,2}(:\d{2})?\s*(am|pm)?|noon|morning|evening|tonight|hour|minute)\b", text, re.I)
    ) and "tomorrow" in text.lower() and not re.search(r"\d", text)

    return ParsedDateTime(
        dt_utc=to_utc(parsed),
        timezone=timezone_name,
        local_dt=parsed,
        recurrence_rule=recurrence,
        offset_minutes=offset,
        ambiguous=ambiguous,
        source=text,
    )


def parse_iso_or_natural(
    value: str,
    *,
    timezone_name: str = "Asia/Kolkata",
    now: datetime | None = None,
) -> ParsedDateTime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        zone = get_zone(timezone_name)
        local = ensure_aware(dt, zone if dt.tzinfo is None else ZoneInfo(str(dt.tzinfo))) if dt.tzinfo is None else dt
        if dt.tzinfo is None:
            local = dt.replace(tzinfo=zone)
        else:
            local = dt.astimezone(zone)
        return ParsedDateTime(dt_utc=to_utc(local), timezone=timezone_name, local_dt=local, source=raw)
    except ValueError:
        return parse_natural_datetime(raw, timezone_name=timezone_name, now=now)


def next_recurrence(dt_utc: datetime, rule: str) -> datetime:
    if rule.startswith("FREQ=DAILY"):
        return dt_utc + timedelta(days=1)
    if "FREQ=WEEKLY" in rule:
        return dt_utc + timedelta(days=7)
    return dt_utc + timedelta(days=1)
