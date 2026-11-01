"""Patrols at fixed local times: which time is due now, which one comes next."""

from __future__ import annotations

from datetime import datetime, timedelta
import re

TIME_RE = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')


class ScheduleError(ValueError):
    """A time is not "HH:MM"."""


def parse_times(times) -> list[tuple[int, int]]:
    """Return the sorted (hour, minute) of "HH:MM" texts (empty entries ignored)."""
    out = []
    for item in times:
        text = str(item).strip()
        if not text:
            continue
        match = TIME_RE.match(text)
        if not match:
            raise ScheduleError(f'{text!r}: use "HH:MM"')
        out.append((int(match.group(1)), int(match.group(2))))
    return sorted(set(out))


def due(now: datetime, times, window_min: float, fired: set) -> datetime | None:
    """Return the slot due at now (within window_min after it) that has not fired, or None."""
    for hour, minute in parse_times(times):
        for day in (now.date(), now.date() - timedelta(days=1)):
            slot = datetime(day.year, day.month, day.day, hour, minute)
            if slot <= now <= slot + timedelta(minutes=window_min) and slot not in fired:
                return slot
    return None


def next_slot(now: datetime, times) -> datetime | None:
    """Return the next slot after now, None without times."""
    slots = []
    for hour, minute in parse_times(times):
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        slots.append(slot if slot > now else slot + timedelta(days=1))
    return min(slots, default=None)
