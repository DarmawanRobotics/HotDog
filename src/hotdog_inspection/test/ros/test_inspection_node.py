"""inspection_node against a fake unipod_driver: inspect a taught point, teach a new target."""

from __future__ import annotations

import os
import time

import pytest

rclpy = pytest.importorskip('rclpy')

from hotdog_inspection.core import plan as plans  # noqa: E402
from hotdog_inspection.inspection_node import InspectionNode  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from sensor_msgs.msg import Image  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402
from unipod_msgs.msg import GimbalAttitude, GimbalStatus, ThermalData  # noqa: E402
from unipod_msgs.srv import (  # noqa: E402
    GetTemperature,
    Recenter,
    SetGimbalAngle,
    SetZoom,
    ThermalControl,
)

from dharma_interfaces.msg import SiteStatus, StopPointEvent  # noqa: E402
from dharma_utils.ros import EVENTS, LATCHED, SENSOR, compat  # noqa: E402
from dharma_utils.testing import Collector, Spinner, wait_for  # noqa: E402
from hotdog_interfaces.msg import Finding, InspectionReport  # noqa: E402
from hotdog_interfaces.srv import AddTarget  # noqa: E402

HOT_STRIP = (213, 0, 426, 511)
PLAN = plans.Plan(
    (
        plans.Point(
            'bay1',
            1.0,
            2.0,
            (plans.Target('ds', 30.0, -10.0, 3.0, plans.ThermalTarget(strips=3)),),
        ),
    )
)


class FakePod:
    """The services and topics of unipod_driver, a hot middle strip."""

    def __init__(self, node):
        self.node = node
        self.calls = []
        ns = '/unipod'
        node.create_service(SetGimbalAngle, f'{ns}/set_angle', self.set_angle)
        node.create_service(SetZoom, f'{ns}/set_zoom', self.ok('set_zoom'))
        node.create_service(ThermalControl, f'{ns}/thermal_control', self.ok('thermal'))
        node.create_service(Recenter, f'{ns}/recenter', self.ok('recenter'))
        node.create_service(GetTemperature, f'{ns}/get_temperature', self.temperature)
        self.status = node.create_publisher(GimbalStatus, f'{ns}/status', 10)
        self.attitude = node.create_publisher(GimbalAttitude, f'{ns}/attitude', SENSOR)
        self.images = [node.create_publisher(Image, f'{ns}/{t}', SENSOR)
                       for t in ('sub/image_raw', 'main/image_raw')]  # fmt: skip
        node.create_timer(0.1, self.tick)

    def ok(self, name):
        def handler(_request, response):
            self.calls.append(name)
            response.success = True
            return response

        return handler

    def set_angle(self, request, response):
        self.calls.append(('set_angle', request.yaw, request.pitch))
        response.success = True
        return response

    def temperature(self, request, response):
        box = (request.x, request.y, request.x2, request.y2)
        hot = request.mode == GetTemperature.Request.REGION and box == HOT_STRIP
        response.success = True
        response.data = ThermalData(mode=request.mode, temp_max=75.0 if hot else 36.0,
                                    temp_min=25.0, max_x=320, max_y=200)  # fmt: skip
        return response

    def tick(self):
        self.status.publish(GimbalStatus(connected=True, zoom=3.0, zoom_max=30.0))
        self.attitude.publish(GimbalAttitude(yaw=-15.0, pitch=-5.0))
        image = Image(height=4, width=4, encoding='bgr8', step=12, data=[0] * 48)
        for pub in self.images:
            pub.publish(image)


@pytest.fixture
def rig(tmp_path):
    compat.init()
    sites, reports = tmp_path / 'sites', tmp_path / 'reports'
    plans.save(plans.plan_path(str(sites), 'gi_test'), PLAN)
    node = InspectionNode(
        parameter_overrides=[
            Parameter('sites_dir', value=str(sites)),
            Parameter('reports_dir', value=str(reports)),
            Parameter('pod.settle_sec', value=0.0),
            Parameter('thermal.samples', value=1),
        ]
    )
    helper = rclpy.create_node('inspection_test_helper')
    pod = FakePod(helper)
    reports_seen = Collector(helper, InspectionReport, 'inspection/report', EVENTS)
    helper.create_publisher(SiteStatus, 'site/status', LATCHED).publish(SiteStatus(site='gi_test'))
    stops = helper.create_publisher(StopPointEvent, 'navigation/stop_point', EVENTS)
    inspect = helper.create_client(Trigger, 'inspection/inspect')
    teach = helper.create_client(AddTarget, 'inspection/add_target')
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    executor.add_node(helper)
    spinner = Spinner(executor)
    assert wait_for(lambda: node.site == 'gi_test' and node.pod.pose() is not None, 5.0)
    assert wait_for(lambda: stops.get_subscription_count() > 0, 5.0)
    stops.publish(StopPointEvent(event=StopPointEvent.ARRIVED, x=1.2, y=2.1))
    assert wait_for(lambda: node.stop is not None, 5.0)
    yield node, spinner, pod, reports_seen, inspect, teach, sites
    spinner.stop()
    helper.destroy_node()
    node.destroy_node()
    compat.try_shutdown()


def test_inspect_finds_the_hot_phase(rig):
    _, spinner, pod, reports_seen, inspect, _, _ = rig
    answer = spinner.call(inspect, Trigger.Request(), timeout=30.0)
    assert answer.success, answer.message
    assert ('set_angle', 30.0, -10.0) in pod.calls and 'recenter' in pod.calls
    assert wait_for(lambda: reports_seen.last is not None, 5.0)
    msg = reports_seen.last
    assert (msg.point, msg.state, msg.severity) == (
        'bay1',
        InspectionReport.DONE,
        Finding.CRITICAL,
    )
    similar = next(f for f in msg.findings if f.criterion == 'similar')
    assert similar.label == 'strip2' and similar.delta == pytest.approx(39.0)
    assert os.path.isfile(os.path.join(msg.directory, 'report.json'))
    assert {os.path.basename(f) for f in similar.files} == {'ds_thermal.jpg', 'ds_visible.jpg'}


def test_stop_without_a_point_passes(rig):
    node, spinner, _, _, inspect, _, _ = rig
    node.stop = (50.0, 50.0, time.monotonic())
    answer = spinner.call(inspect, Trigger.Request(), timeout=10.0)
    assert answer.success and 'no inspection point' in answer.message


def test_teach_a_target_at_the_stop(rig):
    _, spinner, _, _, _, teach, sites = rig
    request = AddTarget.Request(name='ct_terminal', thermal=True, acoustic=False)
    answer = spinner.call(teach, request, timeout=10.0)
    assert answer.success, answer.message
    assert (answer.point, answer.targets) == ('bay1', 2)
    saved = plans.load(plans.plan_path(str(sites), 'gi_test'))
    ct = saved.points[0].targets[1]
    assert (ct.pan_deg, ct.tilt_deg, ct.zoom) == (-15.0, -5.0, 3.0)
    again = spinner.call(teach, request, timeout=10.0)
    assert not again.success and 'already' in again.message
