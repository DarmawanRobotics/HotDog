"""
One patrol: its start sequence, its progress from the follower's status, its findings.

The start steps are plain callables returning (ok, message), run in order until one fails, so
the sequence is tested without ROS. The follower's states are mirrored from
dharma_interfaces/NavigationStatus (core stays free of messages).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class State(IntEnum):
    """hotdog_interfaces/PatrolStatus states."""

    IDLE = 0
    STARTING = 1
    RUNNING = 2
    DONE = 3
    FAILED = 4
    STOPPED = 5


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

    @property
    def busy(self) -> bool:
        """Return True while starting or running."""
        return self.state in (State.STARTING, State.RUNNING)

    def on_navigation(self, nav_state: int, message: str = '') -> bool:
        """Follow the follower; return True when the patrol just ended."""
        if self.state is not State.RUNNING:
            return False
        if nav_state in NAV_ACTIVE:
            self.active = True
            return False
        ends = {
            NAV_GOAL_REACHED: (State.DONE, 'the end of the route was reached'),
            NAV_FAILED: (State.FAILED, f'the follower failed: {message}'),
            NAV_INACTIVE: (State.STOPPED, 'the follower was stopped'),
        }
        # a state left from before this patrol's start (not active yet) ends nothing
        if not self.active or nav_state not in ends:
            return False
        return self.end(*ends[nav_state])

    def on_report(self, severities: list[int]):
        """Count an inspected point and its findings."""
        if self.state is not State.RUNNING:
            return
        self.points += 1
        for severity in severities:
            name = SEVERITY_NAMES[max(0, min(3, int(severity)))]
            self.counts[name] += 1
            self.worst = max(self.worst, int(severity))

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
        }


def route_path(site: str, route: str) -> str:
    """Return the route file relative to sites_dir: <site>/routes/<route>.csv ('' stays '')."""
    route = route.strip()
    if not route:
        return ''
    name = route if route.endswith('.csv') else f'{route}.csv'
    if '/' in name or name.startswith('.'):
        raise ValueError(f"route {route!r}: a file name in the site's routes/, not a path")
    return f'{site}/routes/{name}'
