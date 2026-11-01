"""patrol/status from the session, the battery and the schedule."""

from __future__ import annotations

from datetime import datetime
import time

from hotdog_interfaces.msg import PatrolStatus
from hotdog_patrol.core.config import ScheduleConfig
from hotdog_patrol.core.schedule import ScheduleError, next_slot
from hotdog_patrol.core.session import Session


def status_msg(s: Session, battery: float | None, schedule: ScheduleConfig) -> PatrolStatus:
    """Return the PatrolStatus of a session (header left to the caller)."""
    msg = PatrolStatus(state=int(s.state), site=s.site, route=s.route, started=s.started,
                       points=s.points, worst=s.worst, report=s.report, message=s.message,
                       returned=s.returned)  # fmt: skip
    msg.attention, msg.warning, msg.critical = (
        s.counts['attention'], s.counts['warning'], s.counts['critical'])  # fmt: skip
    msg.elapsed_sec = float(time.time() - s.started) if s.busy else 0.0
    msg.battery = float(battery) if battery is not None else -1.0
    msg.schedule_enabled = schedule.enabled
    try:
        nxt = next_slot(datetime.now(), schedule.times) if schedule.enabled else None
    except ScheduleError:
        nxt = None
    msg.next_scheduled = nxt.strftime('%H:%M') if nxt else ''
    return msg
