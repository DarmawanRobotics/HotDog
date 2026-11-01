"""Partial discharge: the camera client and one detection against a stand-in camera."""

from __future__ import annotations

import dataclasses
import hashlib

from fake_hertzino import Camera, FakeHertzino
from hotdog_inspection.core import discharge
from hotdog_inspection.core.config import AcousticConfig
from hotdog_inspection.core.discharge import AcousticCheck, Detector, finding, judge
from hotdog_inspection.core.hertzino import (
    HertzinoClient,
    HertzinoError,
    password_hash,
    plain,
    types_of,
)
from hotdog_inspection.core.plan import AcousticTarget, Target, ThermalTarget
from hotdog_inspection.core.runner import TargetResult
from hotdog_inspection.core.thermal import Severity
import pytest

CONFIG = AcousticConfig(duration_sec=1.0, margin_sec=5.0, photo_wait_sec=1.0)
TARGET = Target('pd', 0, 0, thermal=ThermalTarget(enabled=False),
                acoustic=AcousticTarget(enabled=True))  # fmt: skip


@pytest.fixture(autouse=True)
def fast_polls(monkeypatch):
    monkeypatch.setattr(discharge, 'POLL_SEC', 0.1)


def client(fake, password='123456'):
    return HertzinoClient('127.0.0.1', fake.port, 'admin', password, timeout=2.0)


def test_password_hash_is_the_manuals():
    assert password_hash('123456') == '7cb8406e5a99c917a60681762d7952c2'
    assert password_hash('x') == hashlib.md5(b'xlfxs').hexdigest()


def test_names_and_types():
    assert plain('20230407_143129') and plain('sm.jpg')
    assert not plain('../etc') and not plain('a/b') and not plain('..')
    assert types_of(1) == ['noise'] and types_of(10) == ['corona', 'floating']


def test_login_and_relogin_after_401():
    with FakeHertzino() as fake:
        c = client(fake)
        assert c.system()['work_mode'] == 1
        fake.camera.expire_token = True
        assert c.detecting() is False  # 401, login again, retried
        assert fake.camera.calls.count(('POST', '/login')) == 2
        with pytest.raises(HertzinoError):
            client(fake, password='wrong').system()
        with pytest.raises(HertzinoError, match='plain'):
            c.file('../x', 'a.jpg')


def test_unreachable_camera():
    c = HertzinoClient('127.0.0.1', 9, 'admin', '123456', timeout=0.5)
    with pytest.raises(HertzinoError):
        c.system()


def test_one_detection_after_the_start(tmp_path):
    with FakeHertzino(Camera(status=2)) as fake:
        fake.camera.detecting = True  # continuous monitoring was running: restarted first
        detector = Detector(client(fake), CONFIG)
        record = detector.detect(1.0)
        # record 8 came from the monitoring that ran before: only 9 was measured after the start
        assert 8 in [r['id'] for r in fake.camera.records]
        assert record['id'] == 9 and record['status'] == 2
        assert fake.camera.duration == 1 and not fake.camera.detecting
        files = detector.photos(record, str(tmp_path / 'pd'))
        assert [f.rsplit('/', 1)[1] for f in files] == ['pd_soundmap.jpg', 'pd_prpd.jpg']


def test_leak_mode_is_refused():
    with FakeHertzino(Camera(mode=2)) as fake, pytest.raises(HertzinoError, match='gas leak'):
        Detector(client(fake), CONFIG).detect(1.0)


def test_judge_types_and_intensity():
    assert judge({'status': 1}, CONFIG) == (Severity.NORMAL, 'noise')
    assert judge({'status': 2}, CONFIG) == (Severity.ATTENTION, 'corona')
    assert judge({'status': 6}, CONFIG) == (Severity.WARNING, 'corona+surface')
    assert judge({'status': 8}, CONFIG)[0] is Severity.CRITICAL
    loud = dataclasses.replace(CONFIG, intensity_warning=30.0, intensity_critical=60.0)
    assert judge({'status': 2, 'soundmap_intensity': 40}, loud)[0] is Severity.WARNING
    assert judge({'status': 2, 'soundmap_intensity': 70}, loud)[0] is Severity.CRITICAL
    assert judge({'status': 1, 'soundmap_intensity': 70}, loud)[0] is Severity.NORMAL
    f = finding(TARGET, {'status': 2, 'soundmap_intensity': 42, 'corona_prob': 0.8}, CONFIG)
    assert (f.sensor, f.criterion, f.label, f.value) == ('acoustic', 'discharge', 'corona', 42.0)
    assert 'corona 0.80' in f.message


def test_check_fills_the_outcome(tmp_path):
    with FakeHertzino(Camera(status=8)) as fake:
        check = AcousticCheck(Detector(client(fake), CONFIG), CONFIG)
        outcome = TargetResult('pd')
        check(TARGET, str(tmp_path / 'pd'), outcome)
        assert outcome.measured and not outcome.errors
        assert outcome.findings[0].severity is Severity.CRITICAL
        assert len(outcome.files) == 2


def test_check_reports_errors_and_skips():
    check = AcousticCheck(Detector(HertzinoClient('127.0.0.1', 9, 'a', 'b', 0.5), CONFIG), CONFIG)
    outcome = TargetResult('pd')
    check(TARGET, '/tmp/x', outcome)
    assert not outcome.measured and outcome.errors[0].startswith('acoustic:')
    off = AcousticCheck(check.detector, dataclasses.replace(CONFIG, enabled=False))
    outcome = TargetResult('pd')
    off(TARGET, '/tmp/x', outcome)
    assert outcome.errors == ['acoustic: off']
    thermal_only = Target('t', 0, 0)
    outcome = TargetResult('t')
    check(thermal_only, '/tmp/x', outcome)
    assert outcome.errors == [] and outcome.findings == []
