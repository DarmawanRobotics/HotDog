"""report_node: a page when a patrol ends, the day refreshed by an inspection, a rebuild."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

rclpy = pytest.importorskip('rclpy')

from hotdog_reports.report_node import ReportNode  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402

from dharma_utils.ros import EVENTS, LATCHED, compat  # noqa: E402
from dharma_utils.testing import Spinner, wait_for  # noqa: E402
from hotdog_interfaces.msg import InspectionReport, PatrolStatus  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
from tree import two_rounds  # noqa: E402


@pytest.fixture
def rig(tmp_path):
    compat.init()
    first, second = two_rounds(str(tmp_path))
    node = ReportNode(parameter_overrides=[
        Parameter('reports_dir', value=str(tmp_path)),
        Parameter('server.enabled', value=False)])  # fmt: skip
    helper = rclpy.create_node('report_test_helper')
    status = helper.create_publisher(PatrolStatus, 'patrol/status', LATCHED)
    reports = helper.create_publisher(InspectionReport, 'inspection/report', EVENTS)
    rebuild = helper.create_client(Trigger, 'reports/rebuild')
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    executor.add_node(helper)
    spinner = Spinner(executor)
    yield tmp_path, (first, second), status, reports, rebuild, spinner
    spinner.stop()
    helper.destroy_node()
    node.destroy_node()
    compat.try_shutdown()


def test_missing_pages_are_rendered_after_start(rig):
    tmp_path, (first, second), *_ = rig
    for summary in (first, second):
        assert wait_for(lambda s=summary: os.path.isfile(s[:-5] + '.html'), 10.0)
    assert (tmp_path / 'index.html').is_file()


def test_a_finished_patrol_and_an_inspection_render_their_pages(rig):
    tmp_path, (_, second), status, reports, _, _ = rig
    assert wait_for(lambda: os.path.isfile(second[:-5] + '.html'), 10.0)
    os.remove(second[:-5] + '.html')
    status.publish(PatrolStatus(state=PatrolStatus.DONE, report=second))
    assert wait_for(lambda: os.path.isfile(second[:-5] + '.html'), 10.0)
    os.remove(tmp_path / '20261101' / 'index.html')
    folder = str(tmp_path / '20261101' / '090200_bay1')
    reports.publish(InspectionReport(point='bay1', directory=folder))
    assert wait_for((tmp_path / '20261101' / 'index.html').is_file, 10.0)


def test_rebuild(rig):
    *_, rebuild, spinner = rig
    answer = spinner.call(rebuild, Trigger.Request())
    assert answer.success and answer.message.startswith('2 patrol pages'), answer.message
