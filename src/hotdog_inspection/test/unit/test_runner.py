"""The point sequence against a fake pod: order, samples, deadline, failures, reports."""

from __future__ import annotations

import dataclasses
from datetime import datetime
import json
import os

from hotdog_inspection.core import report
from hotdog_inspection.core.config import InspectionConfig, PodConfig
from hotdog_inspection.core.plan import AcousticTarget, Point, Target, ThermalTarget
from hotdog_inspection.core.runner import Pod, Runner
from hotdog_inspection.core.thermal import Reading, Severity, worst


class FakePod(Pod):
    """Answers with fixed temperatures per box, records every call."""

    def __init__(self, temps=None, fail_point=False, online=True):
        self.temps = temps or {}
        self.fail_point = fail_point
        self.online = online
        self.calls = []

    def connected(self):
        return self.online

    def point(self, pan_deg, tilt_deg, zoom):
        self.calls.append(('point', pan_deg, tilt_deg, zoom))
        return 'no answer' if self.fail_point or not self.online else ''

    def refresh_shutter(self):
        self.calls.append(('shutter',))
        return ''

    def measure(self, box):
        self.calls.append(('measure', box))
        if not self.online:
            return None, 'pod offline'
        t = self.temps.get(box, 35.0)
        return Reading('x', t, 25.0, 1, 2), ''

    def snapshot(self, prefix):
        self.calls.append(('snapshot', prefix))
        return [f'{prefix}_thermal.jpg', f'{prefix}_visible.jpg']

    def recenter(self):
        self.calls.append(('recenter',))
        return ''


class Clock:
    """A clock the fake sleep advances."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def runner(fake, **config):
    clock = Clock()
    cfg = dataclasses.replace(InspectionConfig(), **config)
    return Runner(cfg, fake, clock=clock, sleep=clock.sleep), clock


POINT = Point(
    'bay1',
    1.0,
    2.0,
    (
        Target('phases', 30.0, -10.0, 3.0, ThermalTarget(strips=3)),
        Target('ct', -20.0, 0.0, 1.0, ThermalTarget()),
    ),
)


def prefix(target):
    return f'/r/{target.name}'


def test_every_target_in_order_with_evidence():
    pod = FakePod()
    run, _ = runner(pod)
    result = run.inspect(POINT, prefix)
    kinds = [c[0] for c in pod.calls]
    assert kinds[0] == 'shutter' and kinds[-1] == 'recenter'
    assert pod.calls[1] == ('point', 30.0, -10.0, 3.0)
    assert kinds.count('measure') == 3 * 3 + 3  # 3 strips x 3 samples, then the frame x 3
    assert result.state == 'done'
    assert result.targets[0].files == ['/r/phases_thermal.jpg', '/r/phases_visible.jpg']
    assert worst(result.findings) is Severity.NORMAL


def test_hot_strip_is_found():
    hot = {(213, 0, 426, 511): 70.0}
    run, _ = runner(FakePod(temps=hot))
    result = run.inspect(POINT, prefix)
    similar = next(f for f in result.findings if f.criterion == 'similar')
    assert similar.label == 'strip2'
    assert similar.severity is Severity.CRITICAL


def test_pod_failure_is_reported_not_raised():
    run, _ = runner(FakePod(fail_point=True))
    result = run.inspect(POINT, prefix)
    assert result.state == 'failed'
    assert 'pod: no answer' in result.message


def test_offline_pod():
    run, _ = runner(FakePod(online=False))
    result = run.inspect(POINT, prefix)
    assert result.state == 'failed'


def test_deadline_skips_the_rest():
    run, _ = runner(FakePod(), max_duration_sec=5.0, pod=PodConfig(settle_sec=4.0))
    result = run.inspect(POINT, prefix)  # settle 4 s + 3 x 2 sample intervals of 0.3 s > 5 s
    assert result.targets[0].measured
    assert result.targets[1].errors == ['skipped: over 5 s']
    assert result.state == 'partial'


def test_cancel():
    run, _ = runner(FakePod())
    assert run.inspect(POINT, prefix, cancelled=lambda: True).state == 'failed'


def test_no_targets_and_nothing_enabled():
    run, _ = runner(FakePod())
    assert run.inspect(Point('empty', 0, 0), prefix).state == 'no_targets'
    idle = Point('idle', 0, 0, (Target('t', 0, 0, thermal=ThermalTarget(enabled=False)),))
    assert run.inspect(idle, prefix).state == 'done'


def test_acoustic_check_runs_without_pointing_the_pod():
    pod = FakePod()
    run, _ = runner(pod)
    seen = []

    def check(target, file_prefix, outcome):
        seen.append(target.name)
        outcome.measured = True

    run.checks.append(check)
    only = Target('pd', 0, 0, thermal=ThermalTarget(enabled=False),
                  acoustic=AcousticTarget(enabled=True))  # fmt: skip
    result = run.inspect(Point('p', 0, 0, (only,)), prefix)
    assert seen == ['pd'] and result.state == 'done'
    assert 'point' not in [c[0] for c in pod.calls]


def test_report_folder_json_and_table(tmp_path):
    run, _ = runner(FakePod(temps={(213, 0, 426, 511): 70.0}))
    result = run.inspect(POINT, prefix)
    when = datetime(2026, 11, 1, 9, 30, 5)
    folder = report.report_dir(str(tmp_path), when, 'bay1')
    again = report.report_dir(str(tmp_path), when, 'bay1')
    assert folder.endswith('20261101/093005_bay1') and again.endswith('093005_bay1_2')
    data = report.to_dict(result, 'gi_cawang', 1.0, 2.0, when)
    report.write(folder, data)
    saved = json.loads((tmp_path / '20261101' / '093005_bay1' / 'report.json').read_text())
    assert saved['severity'] == 'critical' and saved['state'] == 'done'
    assert saved['targets'][0]['files'] == ['phases_thermal.jpg', 'phases_visible.jpg']
    report.write(again, data)
    rows = (tmp_path / '20261101' / 'findings.csv').read_text().splitlines()
    assert rows[0].startswith('time,site,point,target')
    assert len(rows) == 1 + 2 * len(result.findings)
    assert os.path.basename(report.evidence_prefix(folder, 'ct')) == 'ct'
