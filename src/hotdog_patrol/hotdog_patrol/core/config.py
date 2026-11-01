"""Configuration of patrol_node: the start sequence, the watchdog, the schedule, reports."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_utils.config import nested, param


@dataclass(frozen=True)
class StartConfig:
    """What happens before the follower starts (each step is skipped when its service is '')."""

    min_battery: float = param(
        0.3, min=0.0, max=1.0, doc='battery fraction needed to start (0: no check)'
    )
    reanchor: bool = param(
        True, doc='localization/assume_origin first: the patrol starts at the dock'
    )
    stand_up_service: str = param(
        '/{robot_ns}/stand_up', doc='Trigger before the start ({robot_ns} replaced); empty: none'
    )
    stand_up_timeout_sec: float = param(
        20.0, min=1.0, max=120.0, unit='s', doc='the robot stands up and switches to RL control'
    )
    call_timeout_sec: float = param(
        10.0, min=0.5, max=120.0, unit='s', doc='every other service of the sequence'
    )
    max_health: int = param(
        1, min=0, max=2, doc='highest health/status level to start with (0 OK, 1 WARN, 2 ERROR)'
    )


@dataclass(frozen=True)
class FinishConfig:
    """What happens after the route's end was reached."""

    dock_service: str = param(
        '/{robot_ns}/charge_start',
        doc='Trigger after a finished patrol (the M20 docks); empty: none',
    )


@dataclass(frozen=True)
class AbortConfig:
    """The watchdog of a running patrol and the way back to the dock."""

    return_to_dock: bool = param(
        True, doc='a watchdog return walks the taught route back to the dock; false: stop there'
    )
    min_battery: float = param(
        0.2, min=0.0, max=1.0, doc='below this during a patrol: back to the dock (0: off)'
    )
    max_duration_min: float = param(
        120.0, min=0.0, max=1440.0, unit='min', doc='a longer patrol goes back (0: off)'
    )
    hold_timeout_sec: float = param(
        180.0,
        min=0.0,
        max=3600.0,
        unit='s',
        doc='blocked this long: back to the dock; off the route or lost: stop (0: off)',
    )
    nav_timeout_sec: float = param(
        5.0, min=0.0, max=60.0, unit='s', doc='no navigation/status this long: fail (0: off)'
    )
    near_m: float = param(
        2.0, min=0.2, max=10.0, unit='m', doc='waypoints this near can start the return'
    )
    dock_clearance_m: float = param(
        1.0, min=0.0, max=5.0, unit='m', doc='the return ends this far from the route start'
    )
    pose_timeout_sec: float = param(
        2.0, min=0.1, max=10.0, unit='s', doc='the map -> base pose for the return'
    )


@dataclass(frozen=True)
class ScheduleConfig:
    """Patrols at fixed local times of the day."""

    enabled: bool = param(False, doc='live: start patrols at the times below')
    times: tuple[str, ...] = param(
        ('',), doc='local times "HH:MM", e.g. ["06:00", "14:00", "22:00"]'
    )
    route: str = param('', doc='route of the scheduled patrols; empty: the route loaded last')
    window_min: float = param(
        10.0, min=1.0, max=120.0, unit='min', doc='a time missed by more than this is skipped'
    )


@dataclass(frozen=True)
class PatrolConfig:
    """Everything patrol_node reads."""

    sites_dir: str = param('~/.hotdog/sites', live=False, doc='routes: <site>/routes/*.csv')
    reports_dir: str = param('~/.hotdog/reports', live=False, doc='<day>/patrol_<time>.json')
    robot_ns: str = param('m20', live=False, doc='the robot driver namespace ({robot_ns} below)')
    battery_topic: str = param('/{robot_ns}/battery', live=False, doc='sensor_msgs/BatteryState')
    start: StartConfig = nested(StartConfig)
    finish: FinishConfig = nested(FinishConfig)
    abort: AbortConfig = nested(AbortConfig)
    schedule: ScheduleConfig = nested(ScheduleConfig)


def with_ns(name: str, robot_ns: str) -> str:
    """Return a topic or service name with {robot_ns} replaced."""
    return name.replace('{robot_ns}', robot_ns.strip('/'))
