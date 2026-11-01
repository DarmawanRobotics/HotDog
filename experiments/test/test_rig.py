from __future__ import annotations

import math

import common  # noqa: F401
from common.metrics import box_clearance, summary
from common.mux import MuxV01, MuxV02
from common.perception import PerceptionV01, PerceptionV02
from common.rig import Rig
from common.worlds import robot, world
import numpy as np

from dharma_utils.math import Pose2D


def test_box_clearance():
    fp = robot().footprint
    circles = np.array([[1.0, 0.0, 0.25, 1.7], [0.0, 2.0, 0.5, 1.7]])
    assert math.isclose(box_clearance(fp, Pose2D(), circles), 1.0 - 0.4 - 0.25)
    assert box_clearance(fp, Pose2D(), np.empty((0, 4))) == math.inf
    assert box_clearance(fp, Pose2D(), np.array([[0.1, 0.0, 0.2, 1.0]])) < 0.0


def test_summary_ignores_non_finite():
    s = summary([1.0, 3.0, math.inf, math.nan])
    assert s['n'] == 2
    assert s['mean'] == 2.0


def test_rig_drives_straight_and_stops_on_watchdog():
    rig = Rig(world('hall'), robot(), 1)
    rig.driver = lambda r, now: (0.4, 0.0, 0.0) if 1.0 <= now < 3.0 else None
    rig.run(5.0)
    data = rig.trace.arrays()
    assert data['pose'][-1, 0] > 0.5
    assert data['twist'][-1, 0] == 0.0  # the mux zeroed the silent navigation


def test_v01_reads_an_all_zero_scan_as_free():
    profile = robot()
    blind = np.zeros((10, 3), dtype=np.float32)
    old, new = PerceptionV01(profile), PerceptionV02(profile)
    scan_old = old.process(1.0, blind, Pose2D(), 1.0)
    scan_new = new.process(1.0, blind, Pose2D(), 1.0)
    v01, v02 = MuxV01(profile), MuxV02(profile)
    for mux, scan in ((v01, scan_old), (v02, scan_new)):
        mux.arbiter.tick(1.0)  # navigation re-armed by silence
        mux.update_scan(scan, 1.0)
    assert v01.forward('navigation', (0.5, 0.0, 0.0), 1.05) == (0.5, 0.0, 0.0)
    assert v02.forward('navigation', (0.5, 0.0, 0.0), 1.05) == (0.0, 0.0, 0.0)
