"""patrol_node against a fake stack: the start sequence, the route to its end, the summary."""

from __future__ import annotations

import json

import pytest

rclpy = pytest.importorskip('rclpy')

from geometry_msgs.msg import TransformStamped  # noqa: E402
from hotdog_patrol.patrol_node import PatrolNode  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from sensor_msgs.msg import BatteryState  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster  # noqa: E402

from dharma_interfaces.msg import NavigationStatus, SiteStatus  # noqa: E402
from dharma_interfaces.srv import LoadPath, SetMode  # noqa: E402
from dharma_utils.io import RoutePoint, read_route, write_route  # noqa: E402
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
        self.state = NavigationStatus.INACTIVE
        node.create_timer(0.2, lambda: self.publish(self.state))  # like the follower's tick

    def publish(self, state):
        """Publish navigation/status stamped now, and keep repeating it."""
        self.state = state
        msg = NavigationStatus(state=state)
        msg.header.stamp = self.node.get_clock().now().to_msg()
        self.nav.publish(msg)

    def trigger(self, name, response):
        self.calls.append(name)
        response.success = name not in self.refuse
        response.message = 'refused' if name in self.refuse else 'ok'
        if response.success and name in ('navigation/start', 'navigation/stop'):
            start = name == 'navigation/start'
            self.publish(NavigationStatus.JOINING if start else NavigationStatus.INACTIVE)
        return response

    def set_mode(self, request, response):
        self.calls.append(f'mode {request.mode}')
        response.success = True
        return response

    def load(self, request, response):
        self.calls.append(f'load {request.path}')
        response.success = True
        return response


def robot_at(helper, x: float):
    """Publish map -> base_link with the robot x m along the route."""
    t = TransformStamped()
    t.header.stamp = helper.get_clock().now().to_msg()
    t.header.frame_id, t.child_frame_id = 'map', 'base_link'
    t.transform.translation.x = x
    t.transform.rotation.w = 1.0
    broadcaster = StaticTransformBroadcaster(helper)
    broadcaster.sendTransform(t)
    return broadcaster


@pytest.fixture
def rig(tmp_path, request):
    compat.init()
    sites = tmp_path / 'sites'
    write_route(str(sites / 'gi' / 'routes' / 'r1.csv'),
                [RoutePoint(float(i), 0.0, 0.0) for i in range(11)])  # fmt: skip
    overrides = dict(getattr(request, 'param', {}).get('params', {}))
    node = PatrolNode(parameter_overrides=[
        Parameter('reports_dir', value=str(tmp_path / 'reports')),
        Parameter('sites_dir', value=str(sites)),
        *(Parameter(k, value=v) for k, v in overrides.items())])  # fmt: skip
    helper = rclpy.create_node('patrol_test_helper')
    stack = FakeStack(helper, getattr(request, 'param', {}).get('refuse', ()))
    helper.tf_keepalive = robot_at(helper, 6.0)
    status = Collector(helper, PatrolStatus, 'patrol/status', LATCHED)
    start = helper.create_client(StartPatrol, 'patrol/start')
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    executor.add_node(helper)
    spinner = Spinner(executor)
    assert wait_for(lambda: node.site == 'gi' and node.battery is not None, 5.0)
    helper.sites = sites
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
    stack.publish(NavigationStatus.FOLLOWING)
    stack.publish(NavigationStatus.GOAL_REACHED)
    assert wait_for(lambda: node.session.state.name == 'DONE', 5.0)
    assert wait_for(lambda: '/m20/charge_start' in stack.calls, 5.0)
    assert wait_for(lambda: status.last.state == PatrolStatus.DONE and status.last.report, 5.0)
    with open(status.last.report, encoding='utf-8') as f:
        summary = json.load(f)
    assert summary['findings']['warning'] == 1 and summary['state'] == 'done'


@pytest.mark.parametrize('rig', [{'refuse': ('/m20/stand_up',)}], indirect=True)
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


def test_operator_return_walks_the_route_back_to_the_dock(rig):
    node, spinner, stack, status, start = rig
    helper = stack.node
    assert spinner.call(start, StartPatrol.Request(route='r1')).success
    assert wait_for(lambda: node.session.state.name == 'RUNNING', 10.0)
    stack.publish(NavigationStatus.FOLLOWING)
    back = helper.create_client(Trigger, 'patrol/return')
    answer = spinner.call(back, Trigger.Request())
    assert answer.success, answer.message
    assert wait_for(lambda: 'load gi/patrol/return.csv' in stack.calls, 10.0), stack.calls
    assert wait_for(lambda: stack.calls.count('navigation/start') == 2, 5.0)
    way = read_route(str(helper.sites / 'gi' / 'patrol' / 'return.csv'))
    assert [p.x for p in way] == [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    assert node.session.state.name == 'RETURNING'
    stack.publish(NavigationStatus.FOLLOWING)
    stack.publish(NavigationStatus.GOAL_REACHED)
    assert wait_for(lambda: node.session.state.name == 'STOPPED', 5.0), node.session.message
    assert node.session.returned
    assert wait_for(lambda: '/m20/charge_start' in stack.calls, 5.0)
    assert wait_for(lambda: status.last.returned and status.last.report, 5.0)


@pytest.mark.parametrize('rig', [{'params': {'abort.min_battery': 0.9}}], indirect=True)
def test_a_low_battery_sends_the_patrol_back(rig):
    node, spinner, stack, _, start = rig
    assert spinner.call(start, StartPatrol.Request(route='r1')).success
    assert wait_for(lambda: node.session.state.name == 'RETURNING', 10.0), node.session.message
    assert 'battery 80% below 90%' in node.session.message
    assert wait_for(lambda: 'load gi/patrol/return.csv' in stack.calls, 10.0)


def test_the_last_route_is_used_when_none_is_named(rig):
    node, spinner, stack, _, start = rig
    assert spinner.call(start, StartPatrol.Request(route='r1')).success
    assert wait_for(lambda: node.session.state.name == 'RUNNING', 10.0)
    stop = stack.node.create_client(Trigger, 'patrol/stop')
    assert spinner.call(stop, Trigger.Request()).success
    assert spinner.call(start, StartPatrol.Request(route='')).success
    assert node.session.route == 'gi/routes/r1.csv'
