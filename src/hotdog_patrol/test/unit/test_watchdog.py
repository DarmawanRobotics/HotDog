"""The patrol watchdog and the return flow of a session (no ROS)."""

from __future__ import annotations

from hotdog_patrol.core.config import AbortConfig
from hotdog_patrol.core.session import NAV_GOAL_REACHED, NAV_INACTIVE, Session, State
from hotdog_patrol.core.watchdog import FAIL, KEEP, RETURN, Watchdog, hold_kind

from dharma_utils.config import build

FOLLOWING, PAUSED, BLOCKED, OFF_PATH, NAV_FAILED = 2, 5, 6, 7, 9


def watchdog(**overrides) -> Watchdog:
    dog = Watchdog(build(AbortConfig, overrides))
    dog.reset(0.0)
    return dog


def test_hold_kinds():
    assert hold_kind(FOLLOWING, []) == ''
    assert hold_kind(BLOCKED, []) == 'blocked'
    assert hold_kind(OFF_PATH, []) == 'off_path'
    assert hold_kind(PAUSED, ['localization']) == 'lost'
    assert hold_kind(PAUSED, ['battery']) == 'battery'
    assert hold_kind(PAUSED, ['estop', 'localization']) == 'operator'
    assert hold_kind(PAUSED, ['disarmed']) == 'paused'


def test_a_healthy_patrol_keeps_going():
    dog = watchdog()
    for t in range(0, 600, 1):
        dog.on_navigation(FOLLOWING, [], float(t))
    assert dog.check(600.0, 0.8).action == KEEP


def test_battery_and_duration_send_it_back():
    dog = watchdog(min_battery=0.2, max_duration_min=60.0)
    dog.on_navigation(FOLLOWING, [], 10.0)
    verdict = dog.check(10.0, 0.15)
    assert verdict.action == RETURN and 'battery 15%' in verdict.reason
    assert dog.check(10.0, float('nan')).action == KEEP  # unknown battery
    dog.on_navigation(FOLLOWING, [], 3601.0)
    verdict = dog.check(3601.0, 0.9)
    assert verdict.action == RETURN and '60 min' in verdict.reason
    assert watchdog(min_battery=0.0).check(1.0, 0.01).action == KEEP


def test_holds_time_out():
    dog = watchdog(hold_timeout_sec=100.0)
    dog.on_navigation(BLOCKED, [], 10.0)
    dog.on_navigation(BLOCKED, [], 105.0)
    assert dog.check(105.0, 0.9).action == KEEP
    dog.on_navigation(BLOCKED, [], 111.0)
    verdict = dog.check(111.0, 0.9)
    assert verdict.action == RETURN and verdict.reason.startswith('blocked for 101 s')
    lost = watchdog(hold_timeout_sec=100.0)
    lost.on_navigation(PAUSED, ['localization'], 0.0)
    lost.on_navigation(PAUSED, ['localization'], 101.0)
    assert lost.check(101.0, 0.9).action == FAIL
    moving_again = watchdog(hold_timeout_sec=100.0)
    moving_again.on_navigation(BLOCKED, [], 0.0)
    moving_again.on_navigation(FOLLOWING, [], 90.0)
    moving_again.on_navigation(BLOCKED, [], 95.0)
    moving_again.on_navigation(BLOCKED, [], 150.0)
    assert moving_again.check(150.0, 0.9).action == KEEP  # the timer restarted at 95 s


def test_an_operator_in_charge_is_never_overruled():
    dog = watchdog(hold_timeout_sec=10.0, max_duration_min=1.0, min_battery=0.5)
    dog.on_navigation(PAUSED, ['estop'], 0.0)
    dog.on_navigation(PAUSED, ['estop'], 500.0)
    assert dog.check(500.0, 0.1).action == KEEP


def test_a_silent_follower_fails_the_patrol():
    dog = watchdog(nav_timeout_sec=5.0)
    dog.on_navigation(FOLLOWING, [], 1.0)
    assert dog.check(5.0, 0.9).action == KEEP
    verdict = dog.check(7.0, 0.9)
    assert verdict.action == FAIL and 'silent' in verdict.reason


def test_on_the_way_back_only_holds_count():
    dog = watchdog(hold_timeout_sec=10.0, min_battery=0.5, max_duration_min=1.0)
    dog.on_navigation(FOLLOWING, [], 100.0)
    assert dog.check(100.0, 0.1, returning=True).action == KEEP
    dog.on_navigation(BLOCKED, [], 101.0)
    dog.on_navigation(BLOCKED, [], 112.0)
    verdict = dog.check(112.0, 0.9, returning=True)
    assert verdict.action == FAIL and verdict.reason.startswith('on the way back')


def running() -> Session:
    s = Session(route='gi/routes/r1.csv', site='gi', started=100.0, state=State.RUNNING)
    s.on_navigation(FOLLOWING)
    return s


def test_return_ends_back_at_the_dock():
    s = running()
    assert s.begin_return(State.FAILED, 'battery 15% below 20%')
    assert s.state is State.RETURNING and s.busy
    assert not s.on_navigation(NAV_INACTIVE, stamp=50.0)  # the forward route stopping
    s.ignore_before = 200.0
    assert not s.on_navigation(FOLLOWING, stamp=199.0)  # still the old route
    assert not s.on_navigation(NAV_INACTIVE, stamp=199.5)
    assert not s.on_navigation(FOLLOWING, stamp=201.0)
    assert s.on_navigation(NAV_GOAL_REACHED, stamp=260.0)
    assert s.state is State.FAILED and s.returned
    assert s.message == 'back at the dock: battery 15% below 20%'
    assert s.summary(300.0)['returned'] is True


def test_operator_return_and_a_failed_way_back():
    s = running()
    assert s.begin_return(State.STOPPED, 'operator')
    assert not s.begin_return(State.STOPPED, 'twice')
    s.ignore_before = 0.0
    s.on_navigation(FOLLOWING)
    assert s.on_navigation(NAV_FAILED, 'off path')
    assert s.state is State.FAILED and not s.returned and 'way back failed' in s.message
    idle = Session()
    assert not idle.begin_return(State.STOPPED, 'operator')


def test_reports_count_on_the_way_back_with_their_directories():
    s = running()
    s.on_report([1], '/r/20261101/093000_bay1')
    s.begin_return(State.STOPPED, 'operator')
    s.on_report([3], '/r/20261101/093500_bay2')
    assert s.points == 2 and s.worst == 3
    assert s.summary(200.0)['inspections'] == [
        '/r/20261101/093000_bay1',
        '/r/20261101/093500_bay2',
    ]
