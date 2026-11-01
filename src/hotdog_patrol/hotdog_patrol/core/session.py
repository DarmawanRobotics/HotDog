"""
One patrol: its start sequence, its progress from the follower's status, its findings.

The start steps are plain callables returning (ok, message), run in order until one fails, so
the sequence is tested without ROS. The follower's states are mirrored from
dharma_interfaces/NavigationStatus (core stays free of messages).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import math


class State(IntEnum):
    """hotdog_interfaces/PatrolStatus states."""

    IDLE = 0
    STARTING = 1
    RUNNING = 2
    DONE = 3
    FAILED = 4
    STOPPED = 5
    RETURNING = 6


# dharma_interfaces/NavigationStatus
NAV_INACTIVE, NAV_GOAL_REACHED, NAV_FAILED = 0, 8, 9
NAV_ACTIVE = frozenset(range(1, 8))  # joining ... off path: the follower works on the route
SEVERITY_NAMES = ('normal', 'attention', 'warning', 'critical')


def run_steps(steps) -> tuple[bool, str]:
    """Run (name, fn) steps in order; fn() -> (ok, message). Stop at the first failure."""
    done = []
    for name, fn in steps:
        ok, message = fn()
        if not ok:
            return False, f'{name}: {message}'
        done.append(name)
    return True, ', '.join(done) or 'nothing to do'


@dataclass
class Session:
    """The patrol running or the last one."""

    route: str = ''
    site: str = ''
    started: float = 0.0  # unix time
    state: State = State.IDLE
    message: str = ''
    points: int = 0
    counts: dict = field(default_factory=lambda: dict.fromkeys(SEVERITY_NAMES, 0))
    worst: int = 0
    report: str = ''
    active: bool = False  # the follower was seen working on the route
    returned: bool = False  # ended by walking back to the dock
    final: State = State.FAILED  # the state a return ends in
    reason: str = ''  # why the patrol returns
    inspections: list = field(default_factory=list)  # report directories of the points
    ignore_before: float = 0.0  # s, follower statuses stamped earlier are not this route's
    # (set once the follower accepted the start: a later status is this route's for sure)

    @property
    def busy(self) -> bool:
        """Return True while starting, running or returning."""
        return self.state in (State.STARTING, State.RUNNING, State.RETURNING)

    def on_navigation(self, nav_state: int, message: str = '', stamp: float = 0.0) -> bool:
        """Follow the follower; return True when the patrol just ended."""
        if self.state not in (State.RUNNING, State.RETURNING) or stamp < self.ignore_before:
            return False
        if nav_state in NAV_ACTIVE:
            self.active = True
            return False
        if self.state is State.RETURNING:
            ends = {
                NAV_GOAL_REACHED: (self.final, f'back at the dock: {self.reason}'),
                NAV_FAILED: (State.FAILED, f'the way back failed ({self.reason}): {message}'),
                NAV_INACTIVE: (State.STOPPED, f'the way back was stopped ({self.reason})'),
            }
        else:
            ends = {
                NAV_GOAL_REACHED: (State.DONE, 'the end of the route was reached'),
                NAV_FAILED: (State.FAILED, f'the follower failed: {message}'),
                NAV_INACTIVE: (State.STOPPED, 'the follower was stopped'),
            }
        # a state left from before this patrol's start ends nothing: this route's are the ones
        # after an active state, or stamped after the follower accepted the start
        fresh = self.active or 0.0 < self.ignore_before < math.inf
        if not fresh or nav_state not in ends:
            return False
        self.returned = self.state is State.RETURNING and nav_state == NAV_GOAL_REACHED
        return self.end(*ends[nav_state])

    def on_report(self, severities: list[int], directory: str = ''):
        """Count an inspected point and its findings (one finished on the way back too)."""
        if self.state not in (State.RUNNING, State.RETURNING):
            return
        self.points += 1
        if directory:
            self.inspections.append(directory)
        for severity in severities:
            name = SEVERITY_NAMES[max(0, min(3, int(severity)))]
            self.counts[name] += 1
            self.worst = max(self.worst, int(severity))

    def begin_return(self, final: State, reason: str) -> bool:
        """Turn a running patrol into its way back to the dock; False when none runs."""
        if self.state is not State.RUNNING:
            return False
        self.state, self.final, self.reason = State.RETURNING, final, reason
        self.message, self.active = f'returning to the dock: {reason}', False
        self.ignore_before = math.inf  # until the way back is started
        return True

    def end(self, state: State, message: str) -> bool:
        """End the patrol with a state; True when it was running."""
        if not self.busy:
            return False
        self.state, self.message = state, message
        return True

    def summary(self, now: float) -> dict:
        """Return the JSON of the patrol."""
        return {
            'site': self.site,
            'route': self.route,
            'started': self.started,
            'duration_sec': round(max(0.0, now - self.started), 1),
            'state': self.state.name.lower(),
            'message': self.message,
            'points': self.points,
            'findings': dict(self.counts),
            'worst': SEVERITY_NAMES[self.worst],
            'returned': self.returned,
            'inspections': list(self.inspections),
        }


def start_checks(cfg, health, control, battery: float | None) -> tuple[bool, str]:
    """Return whether a patrol may start: health level, e-stop, battery (cfg: StartConfig)."""
    if health is not None and health.level > cfg.max_health:
        return False, f'health level {health.level}: {"; ".join(health.issues)}'
    if control is not None and control.estop:
        return False, 'the e-stop is engaged'
    if cfg.min_battery > 0.0 and (battery is None or battery < cfg.min_battery):
        return False, f'battery {battery if battery is not None else "unknown"}'
    return True, 'ok'


def route_path(site: str, route: str) -> str:
    """Return the route file relative to sites_dir: <site>/routes/<route>.csv ('' stays '')."""
    route = route.strip()
    if not route:
        return ''
    name = route if route.endswith('.csv') else f'{route}.csv'
    if '/' in name or name.startswith('.'):
        raise ValueError(f"route {route!r}: a file name in the site's routes/, not a path")
    return f'{site}/routes/{name}'
