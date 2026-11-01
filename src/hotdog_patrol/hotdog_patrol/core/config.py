"""Configuration of patrol_node: the start sequence, the schedule, reports."""

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
    schedule: ScheduleConfig = nested(ScheduleConfig)


def with_ns(name: str, robot_ns: str) -> str:
    """Return a topic or service name with {robot_ns} replaced."""
    return name.replace('{robot_ns}', robot_ns.strip('/'))
