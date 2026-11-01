"""patrol_node against a fake stack: the start sequence, the route to its end, the summary."""

from __future__ import annotations

import json

import pytest

rclpy = pytest.importorskip('rclpy')

from hotdog_patrol.patrol_node import PatrolNode  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from sensor_msgs.msg import BatteryState  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402

from dharma_interfaces.msg import NavigationStatus, SiteStatus  # noqa: E402
from dharma_interfaces.srv import LoadPath, SetMode  # noqa: E402
from dharma_utils.ros import EVENTS, LATCHED, SENSOR, compat  # noqa: E402
from dharma_utils.testing import Collector, Spinner, wait_for  # noqa: E402
from hotdog_interfaces.msg import Finding, InspectionReport, PatrolStatus  # noqa: E402
from hotdog_interfaces.srv import StartPatrol  # noqa: E402


class FakeStack:
    """localization, the M20 driver, the control mux and the follower, as services."""

    def __init__(self, node, refuse=()):
        self.node, self.calls, self.refuse = node, [], set(refuse)
        for name in ('localization/assume_origin', '/m20/stand_up', 'navigation/start',
                     'navigation/stop', '/m20/charge_start'):  # fmt: skip
            node.create_service(Trigger, name, lambda q, r, n=name: self.trigger(n, r))
        node.create_service(SetMode, 'control/set_mode', self.set_mode)
        node.create_service(LoadPath, 'navigation/load_path', self.load)
        self.nav = node.create_publisher(NavigationStatus, 'navigation/status', LATCHED)
        self.reports = node.create_publisher(InspectionReport, 'inspection/report', EVENTS)
        self.battery = node.create_publisher(BatteryState, '/m20/battery', SENSOR)
        node.create_publisher(SiteStatus, 'site/status', LATCHED).publish(SiteStatus(site='gi'))
        node.create_timer(0.1, lambda: self.battery.publish(BatteryState(percentage=0.8)))

    def trigger(self, name, response):
        self.calls.append(name)
        response.success = name not in self.refuse
        response.message = 'refused' if name in self.refuse else 'ok'
        if name == 'navigation/start' and response.success:
            self.nav.publish(NavigationStatus(state=NavigationStatus.JOINING))
        return response

    def set_mode(self, request, response):
        self.calls.append(f'mode {request.mode}')
        response.success = True
        return response

    def load(self, request, response):
        self.calls.append(f'load {request.path}')
        response.success = True
        return response


@pytest.fixture
def rig(tmp_path, request):
    compat.init()
    node = PatrolNode(parameter_overrides=[Parameter('reports_dir', value=str(tmp_path))])
    helper = rclpy.create_node('patrol_test_helper')
    stack = FakeStack(helper, getattr(request, 'param', ()))
    status = Collector(helper, PatrolStatus, 'patrol/status', LATCHED)
    start = helper.create_client(StartPatrol, 'patrol/start')
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    executor.add_node(helper)
    spinner = Spinner(executor)
    assert wait_for(lambda: node.site == 'gi' and node.battery is not None, 5.0)
    yield node, spinner, stack, status, start
    spinner.stop()
    helper.destroy_node()
    node.destroy_node()
    compat.try_shutdown()


def test_patrol_from_the_dock_to_the_end_of_the_route(rig):
    node, spinner, stack, status, start = rig
    answer = spinner.call(start, StartPatrol.Request(route='r1'))
    assert answer.success, answer.message
    assert wait_for(lambda: node.session.state.name == 'RUNNING', 10.0)
    assert stack.calls[:5] == ['localization/assume_origin', '/m20/stand_up', 'mode auto',
                               'load gi/routes/r1.csv', 'navigation/start']  # fmt: skip
    finding = Finding(severity=Finding.WARNING)
    stack.reports.publish(InspectionReport(point='bay1', findings=[finding]))
    assert wait_for(lambda: node.session.points == 1, 5.0)
    stack.nav.publish(NavigationStatus(state=NavigationStatus.FOLLOWING))
    stack.nav.publish(NavigationStatus(state=NavigationStatus.GOAL_REACHED))
    assert wait_for(lambda: node.session.state.name == 'DONE', 5.0)
    assert wait_for(lambda: '/m20/charge_start' in stack.calls, 5.0)
    assert wait_for(lambda: status.last.state == PatrolStatus.DONE and status.last.report, 5.0)
    with open(status.last.report, encoding='utf-8') as f:
        summary = json.load(f)
    assert summary['findings']['warning'] == 1 and summary['state'] == 'done'


@pytest.mark.parametrize('rig', [('/m20/stand_up',)], indirect=True)
def test_a_failed_step_fails_the_patrol(rig):
    node, spinner, stack, _, start = rig
    assert spinner.call(start, StartPatrol.Request(route='')).success
    assert wait_for(lambda: node.session.state.name == 'FAILED', 10.0)
    assert node.session.message == 'stand up: refused'
    assert 'navigation/start' not in stack.calls


def test_one_patrol_at_a_time_and_safe_route_names(rig):
    _, spinner, _, _, start = rig
    assert not spinner.call(start, StartPatrol.Request(route='../etc/x')).success
    assert spinner.call(start, StartPatrol.Request(route='r1')).success
    second = spinner.call(start, StartPatrol.Request(route='r1'))
    assert not second.success and 'patrol is' in second.message
