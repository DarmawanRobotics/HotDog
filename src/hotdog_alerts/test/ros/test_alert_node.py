"""alert_node against a stand-in webhook: findings, a finished patrol, health, the test alert."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

rclpy = pytest.importorskip('rclpy')

from hotdog_alerts.alert_node import AlertNode  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402

from dharma_interfaces.msg import HealthStatus  # noqa: E402
from dharma_utils.ros import EVENTS, LATCHED, compat  # noqa: E402
from dharma_utils.testing import Spinner, wait_for  # noqa: E402
from hotdog_interfaces.msg import InspectionReport, PatrolStatus  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
from fake_api import FakeApi  # noqa: E402

REPORT = {
    'site': 'gi', 'point': 'bay1', 'state': 'done', 'severity': 'critical',
    'targets': [{'target': 'bay1_ds', 'files': [], 'findings': [
        {'sensor': 'acoustic', 'criterion': 'discharge', 'label': 'floating',
         'severity': 'critical', 'value': 44.0, 'reference': 0.0, 'delta': 0.0, 'unit': 'dB'}]}],
}  # fmt: skip


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
    api = FakeApi()
    compat.init()
    node = AlertNode(parameter_overrides=[
        Parameter('webhook.url', value=api.base + '/hook'),
        Parameter('spool_dir', value=str(tmp_path / 'spool')),
        Parameter('retry_sec', value=2.0)])  # fmt: skip
    helper = rclpy.create_node('alert_test_helper')
    pubs = {
        'report': helper.create_publisher(InspectionReport, 'inspection/report', EVENTS),
        'patrol': helper.create_publisher(PatrolStatus, 'patrol/status', LATCHED),
        'health': helper.create_publisher(HealthStatus, 'health/status', LATCHED),
    }
    test = helper.create_client(Trigger, 'alerts/test')
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    executor.add_node(helper)
    spinner = Spinner(executor)
    assert wait_for(lambda: all(p.get_subscription_count() > 0 for p in pubs.values()), 10.0)
    yield tmp_path, api, pubs, test, spinner
    spinner.stop()
    helper.destroy_node()
    node.destroy_node()
    compat.try_shutdown()
    api.stop()


def kinds(api) -> list:
    return [r['json']['kind'] for r in api.requests]


def test_a_critical_finding_reaches_the_webhook(rig):
    tmp_path, api, pubs, _, _ = rig
    folder = tmp_path / '20261101' / '090200_bay1'
    folder.mkdir(parents=True)
    (folder / 'report.json').write_text(json.dumps(REPORT))
    pubs['report'].publish(InspectionReport(point='bay1', directory=str(folder)))
    assert wait_for(lambda: 'finding' in kinds(api), 10.0)
    sent = api.requests[0]['json']
    assert sent['severity'] == 'critical' and 'floating' in sent['text']


def test_patrols_after_start_and_health_errors(rig):
    _, api, pubs, _, _ = rig
    old = PatrolStatus(state=PatrolStatus.DONE, report='/r/20261031/patrol_090000.json')
    pubs['patrol'].publish(old)  # ended before the node started: not announced
    new = PatrolStatus(state=PatrolStatus.FAILED, report='/r/20261101/patrol_090000.json',
                       message='lost', site='gi')  # fmt: skip
    pubs['patrol'].publish(new)
    pubs['health'].publish(HealthStatus(level=HealthStatus.ERROR, issues=['odometry stale']))
    assert wait_for(lambda: {'patrol', 'health'} <= set(kinds(api)), 10.0)
    assert kinds(api).count('patrol') == 1
    patrol = next(r['json'] for r in api.requests if r['json']['kind'] == 'patrol')
    assert 'FAILED: lost' in patrol['title']


def test_the_test_alert(rig):
    _, api, _, test, spinner = rig
    answer = spinner.call(test, Trigger.Request())
    assert answer.success, answer.message
    assert wait_for(lambda: 'test' in kinds(api), 10.0)
