"""The patrol's start sequence, its progress, its findings and the schedule (no ROS)."""

from __future__ import annotations

from datetime import datetime

from hotdog_patrol.core.config import PatrolConfig, with_ns
from hotdog_patrol.core.schedule import ScheduleError, due, next_slot, parse_times
from hotdog_patrol.core.session import (
    NAV_FAILED,
    NAV_GOAL_REACHED,
    NAV_INACTIVE,
    Session,
    State,
    route_path,
    run_steps,
)
import pytest

from dharma_utils.config import build

FOLLOWING, DWELLING = 2, 4


def running() -> Session:
    return Session(route='gi/routes/r1.csv', site='gi', started=100.0, state=State.RUNNING)


def test_defaults_and_namespaces():
    cfg = build(PatrolConfig, {})
    assert not cfg.schedule.enabled
    assert with_ns(cfg.start.stand_up_service, 'm20') == '/m20/stand_up'
    assert with_ns(cfg.finish.dock_service, '/m20b/') == '/m20b/charge_start'
    assert with_ns(cfg.battery_topic, 'm20') == '/m20/battery'
    assert with_ns('', 'm20') == ''


def test_steps_stop_at_the_first_failure():
    calls = []

    def step(name, ok):
        return name, lambda: (calls.append(name) or ok, 'refused' if not ok else 'ok')

    ok, message = run_steps([step('checks', True), step('re-anchor', False), step('start', True)])
    assert (ok, message) == (False, 're-anchor: refused')
    assert calls == ['checks', 're-anchor']
    assert run_steps([step('a', True), step('b', True)]) == (True, 'a, b')


def test_route_reached():
    s = running()
    assert not s.on_navigation(NAV_GOAL_REACHED)  # left from the previous patrol: ignored
    assert not s.on_navigation(FOLLOWING)
    assert s.on_navigation(NAV_GOAL_REACHED)
    assert s.state is State.DONE and not s.busy


def test_follower_failed_or_stopped():
    s = running()
    s.on_navigation(FOLLOWING)
    assert s.on_navigation(NAV_FAILED, 'blocked for 60 s')
    assert s.state is State.FAILED and 'blocked' in s.message
    stopped = running()
    assert not stopped.on_navigation(NAV_INACTIVE)  # before it started
    stopped.on_navigation(DWELLING)
    assert stopped.on_navigation(NAV_INACTIVE) and stopped.state is State.STOPPED


def test_findings_are_counted_while_running():
    s = running()
    s.on_report([0, 1, 1])
    s.on_report([3])
    s.on_report([])
    assert (s.points, s.worst) == (3, 3)
    assert s.counts == {'normal': 1, 'attention': 2, 'warning': 0, 'critical': 1}
    s.end(State.STOPPED, 'operator')
    s.on_report([2])
    assert s.points == 3
    summary = s.summary(160.0)
    assert summary['duration_sec'] == 60.0 and summary['worst'] == 'critical'
    assert summary['state'] == 'stopped'


def test_route_paths_stay_in_the_site():
    assert route_path('gi', 'r1') == 'gi/routes/r1.csv'
    assert route_path('gi', 'r1.csv') == 'gi/routes/r1.csv'
    assert route_path('gi', ' ') == ''
    for bad in ('../x', 'a/b', '.hidden'):
        with pytest.raises(ValueError, match='routes'):
            route_path('gi', bad)


def test_schedule_due_once_within_the_window():
    times = ['14:00', '06:00', '']
    assert parse_times(times) == [(6, 0), (14, 0)]
    fired = set()
    now = datetime(2026, 11, 1, 14, 3)
    slot = due(now, times, 10.0, fired)
    assert slot == datetime(2026, 11, 1, 14, 0)
    fired.add(slot)
    assert due(now, times, 10.0, fired) is None
    assert due(datetime(2026, 11, 1, 14, 30), times, 10.0, set()) is None  # missed: skipped
    assert due(datetime(2026, 11, 1, 0, 4), ['23:58'], 10.0, set()) == datetime(
        2026, 10, 31, 23, 58
    )


def test_next_slot_and_bad_times():
    assert next_slot(datetime(2026, 11, 1, 15, 0), ['06:00', '14:00']) == datetime(
        2026, 11, 2, 6, 0
    )
    assert next_slot(datetime(2026, 11, 1, 5, 0), ['06:00']) == datetime(2026, 11, 1, 6, 0)
    assert next_slot(datetime(2026, 11, 1, 5, 0), ['']) is None
    with pytest.raises(ScheduleError):
        parse_times(['25:00'])
