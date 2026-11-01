"""
The patrol watchdog: decides when a running patrol goes back to the dock or stops.

Fed with the follower's state and pause reasons, the battery and monotonic time; core stays
free of ROS (the states and reasons mirror dharma_interfaces/NavigationStatus). An operator in
charge (operator pause, e-stop, remote) is never overruled.
"""

from __future__ import annotations

from dataclasses import dataclass

from hotdog_patrol.core.config import AbortConfig

# dharma_interfaces/NavigationStatus
NAV_PAUSED, NAV_BLOCKED, NAV_OFF_PATH = 5, 6, 7
OPERATOR_HOLDS = frozenset({'operator', 'estop', 'remote'})

KEEP, RETURN, FAIL = '', 'return', 'fail'
HOLD_TEXT = {
    'blocked': 'blocked',
    'off_path': 'off the route',
    'lost': 'not localized',
    'battery': 'paused on a critical battery',
    'paused': 'paused',
}


@dataclass(frozen=True)
class Verdict:
    """What the watchdog wants: keep going, return to the dock or fail where it stands."""

    action: str = KEEP
    reason: str = ''


def hold_kind(state: int, reasons) -> str:
    """Return why the follower holds the robot ('' while it works on the route)."""
    if state != NAV_PAUSED:
        return {NAV_BLOCKED: 'blocked', NAV_OFF_PATH: 'off_path'}.get(state, '')
    reasons = set(reasons)
    if reasons & OPERATOR_HOLDS:
        return 'operator'
    for reason, kind in (('localization', 'lost'), ('battery', 'battery')):
        if reason in reasons:
            return kind
    return 'paused'


class Watchdog:
    """Hold timers, the patrol duration and the follower's heartbeat of one patrol."""

    def __init__(self, config: AbortConfig):
        self.config = config
        self.reset(0.0)

    def reset(self, now: float):
        """Start watching (the patrol runs or its return starts)."""
        self.started = now
        self.last_nav = now
        self.kind = ''
        self.since = now

    def on_navigation(self, state: int, reasons, now: float):
        """Take a navigation/status."""
        self.last_nav = now
        kind = hold_kind(state, reasons)
        if kind != self.kind:
            self.kind, self.since = kind, now

    def check(self, now: float, battery: float | None, returning: bool = False) -> Verdict:
        """Return the verdict now."""
        c = self.config
        silent = now - self.last_nav
        if c.nav_timeout_sec > 0.0 and silent > c.nav_timeout_sec:
            return Verdict(FAIL, f'navigation/status silent for {silent:.0f} s')
        if self.kind == 'operator':
            return Verdict()
        held = self.held(now, returning)
        if held.action or returning:
            return held
        return self.limits(now, battery)

    def held(self, now: float, returning: bool) -> Verdict:
        """Return the verdict of a hold that lasted too long."""
        held = now - self.since
        if not self.kind or self.config.hold_timeout_sec <= 0.0:
            return Verdict()
        if held <= self.config.hold_timeout_sec:
            return Verdict()
        text = f'{HOLD_TEXT[self.kind]} for {held:.0f} s'
        if returning:
            return Verdict(FAIL, f'on the way back: {text}')
        return Verdict(RETURN if self.kind == 'blocked' else FAIL, text)

    def limits(self, now: float, battery: float | None) -> Verdict:
        """Return the verdict of the battery and the patrol duration."""
        c = self.config
        if c.min_battery > 0.0 and battery is not None and 0.0 <= battery < c.min_battery:
            return Verdict(RETURN, f'battery {battery:.0%} below {c.min_battery:.0%}')
        if c.max_duration_min > 0.0 and now - self.started > c.max_duration_min * 60.0:
            return Verdict(RETURN, f'longer than {c.max_duration_min:.0f} min')
        return Verdict()
