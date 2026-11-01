from __future__ import annotations

import math

import common  # noqa: F401
import e1_stopping
import e2_blind
import e3_localization
import e4_path_shift
import e5_backup


def test_e1_stops_with_the_margin():
    row = e1_stopping.run(0.6, 1)
    assert not row.collided
    assert row.travel_m < row.model_m
    assert row.min_clearance_m > 0.1


def test_e2_v02_stops_a_blind_robot_and_v01_does_not():
    new = e2_blind.run('empty', 'auto', 'v0.2', 1)
    old = e2_blind.run('empty', 'auto', 'v0.1', 1)
    assert new.zero_after_sec < 0.2
    assert math.isinf(old.zero_after_sec)
    creep = e2_blind.run('silent', 'remote', 'v0.2', 1)
    assert creep.creep_mps <= 0.15 + 1e-6


def test_e3_one_lap():
    rows = {r.method: r for r in e3_localization.run(1, laps=1)}
    assert set(rows) == set(e3_localization.METHODS)
    for row in rows.values():
        assert math.isfinite(row.ate_m)
        assert row.inliers > 0
    assert rows['ekf_tags_scan'].scan_matches > 0


def test_e4_path_shift_passes_the_people():
    row = e4_path_shift.run('path_shift', 1)
    assert row.completed
    assert row.min_clearance_m > 0.0


def test_e5_backup_stops_short_of_a_person_behind():
    row = e5_backup.run('person', 1)
    assert row.completed
    assert 0.0 < row.backed_m < row.person_gap_m
    assert row.person_clearance_m > 0.3
    assert not row.collided
