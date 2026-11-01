"""The status lines (no ROS)."""

from __future__ import annotations

from hotdog.status import lines, name, paint

SNAPSHOT = {
    'patrol': {'state': 6, 'route': 'gi/routes/r1.csv', 'elapsed_sec': 754.0, 'points': 3,
               'critical': 1, 'warning': 0, 'attention': 2, 'next_scheduled': '14:00',
               'message': 'returning to the dock: battery 18% below 20%'},
    'health': {'level': 1, 'speed_scale': 0.5, 'issues': ['sensor /lidar/rear/points 4 Hz']},
    'localization': {'state': 1, 'source': 'odometry', 'sigma_xy': 0.42},
    'control': {'mode': 0, 'estop': False, 'estop_reasons': [], 'field': 2},
    'battery': 0.18,
    'inspection': {'state': 0, 'pod_connected': True, 'acoustic_connected': False,
                   'ambient_c': 31.0, 'points': 12, 'targets': 30, 'last_point': 'bay3',
                   'last_severity': 3},
    'navigation': {'state': 2, 'pause_reasons': [], 'remaining': 120.4, 'count': 400},
    'alerts': '2 waiting to be sent',
    'reports': 'http://10.21.31.50:8088/',
}  # fmt: skip


def test_every_part_on_one_line():
    text = '\n'.join(lines(SNAPSHOT))
    assert 'patrol      RETURNING  gi/routes/r1.csv 12 min points 3 (C1 W0 A2) next 14:00' in text
    assert 'health      WARN  speed 50% sensor /lidar/rear/points 4 Hz' in text
    assert 'localize    LOCALIZED  (odometry) drift ±0.42 m' in text
    assert 'control     AUTO  e-stop off field LIMITED' in text
    assert 'battery     18%' in text
    assert 'ACOUSTIC MISSING' in text and 'last bay3 critical' in text
    assert 'navigation  FOLLOWING  120 m left' in text
    assert 'reports     http://10.21.31.50:8088/' in text


def test_nothing_received():
    text = '\n'.join(lines({}))
    assert 'patrol      ?  (no message: is hotdog running?' in text
    assert 'battery     ?' in text


def test_names_and_colors():
    assert name(('A', 'B'), 1) == 'B' and name(('A',), 7) == '?' and name(('A',), None) == '?'
    assert paint('ERROR', True) == '\x1b[31mERROR\x1b[0m'
    assert paint('WARN', True).startswith('\x1b[33m') and paint('OK', True).startswith('\x1b[32m')
    assert paint('OK', False) == 'OK'
