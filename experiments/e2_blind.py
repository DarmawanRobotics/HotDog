"""
E2: blind LiDAR in AUTO and REMOTE, v0.2 against the v0.1 reading of a blind scan as free.

The robot drives straight at 0.5 m/s (AUTO: a command stream at 20 Hz; REMOTE: the operator
source, re-armed by neutral commands first). After 5 s (plus a seeded phase) the LiDAR fails
for 4 s: silent (no cloud at all, a dharma_sim dropout), empty (clouds without points) or sparse
(50 points per cloud, below the 100 of the blindness check). Measured: AUTO, the time from the
failure to the first zero command of the mux and the distance to standstill; REMOTE, the speed
of the fastest point of the body once settled (1.5 s after the failure to its end).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import sys

import common  # noqa: F401  (puts the stack on sys.path)
from common.metrics import write_rows
from common.mux import MuxV01, MuxV02
from common.perception import PerceptionV01, PerceptionV02
from common.rig import TICK_SEC, Rig, fastest_point, first_after, speed_of
from common.worlds import SEEDS, robot, world
import numpy as np

from dharma_sim.core.scenario import Dropout, Scenario
from dharma_utils.math import default_rng

KINDS = ('silent', 'empty', 'sparse')
MODES = ('auto', 'remote')
VERSIONS = ('v0.2', 'v0.1')
SPEED = 0.5
START_SEC = 1.0
FAIL_SEC = 5.0
DURATION_SEC = 4.0
SETTLE_SEC = 1.5
SPARSE_POINTS = 50


@dataclass(frozen=True)
class BlindRow:
    """One E2 run."""

    kind: str
    mode: str
    version: str
    seed: int
    zero_after_sec: float
    stop_after_sec: float
    distance_m: float
    creep_mps: float


def degrade(kind: str, start: float, rng: np.random.Generator):
    """Return the scan filter of a failure that starts at start (s)."""

    def scan_filter(now: float, points: np.ndarray):
        if not start <= now < start + DURATION_SEC:
            return points
        if kind == 'empty':
            return points[:0]
        keep = rng.choice(len(points), size=min(SPARSE_POINTS, len(points)), replace=False)
        return points[np.sort(keep)]

    return scan_filter


def build(kind: str, mode: str, version: str, seed: int) -> tuple[Rig, float]:
    """Return the rig of one run and the failure time."""
    profile = robot()
    rng = default_rng([seed, 2])
    start = FAIL_SEC + float(rng.uniform(0.0, 0.1))
    scenario = None
    if kind == 'silent':  # the scenario clock starts at the first physics step (one tick)
        scenario = Scenario(seed=seed, dropouts=(Dropout(start - TICK_SEC, DURATION_SEC),))
    old = version == 'v0.1'
    rig = Rig(
        world('hall'), profile, seed, scenario,
        perception=(PerceptionV01 if old else PerceptionV02)(profile),
        mux=(MuxV01 if old else MuxV02)(profile, mode),
    )  # fmt: skip
    if kind != 'silent':
        rig.scan_filter = degrade(kind, start, rng)
    if mode == 'remote':
        rig.source = rig.mux.config.remote_sources[0]
    rig.driver = lambda r, now: (SPEED, 0.0, 0.0) if now >= START_SEC else (0.0, 0.0, 0.0)
    return rig, start


def run(kind: str, mode: str, version: str, seed: int) -> BlindRow:
    """Run one failure and measure it."""
    rig, start = build(kind, mode, version, seed)
    rig.run(start + DURATION_SEC)
    data = rig.trace.arrays()
    t, x, twist = data['t'], data['pose'][:, 0], data['twist']
    cmd_t, cmd = data['cmd_t'], data['cmd']
    zero = first_after(cmd_t, np.hypot(cmd[:, 0], cmd[:, 1]) <= 1e-9, start)
    stop = first_after(t, speed_of(twist) <= 1e-9, start)
    i0 = int(np.searchsorted(t, start))
    i1 = min(int(np.searchsorted(t, stop)), len(t) - 1)
    settled = (t >= start + SETTLE_SEC) & (t < start + DURATION_SEC)
    fastest = fastest_point(twist[settled], rig.robot.footprint.circumscribed_radius)
    creep = float(fastest.mean()) if mode == 'remote' else math.nan
    return BlindRow(
        kind, mode, version, seed, zero - start, stop - start, float(x[i1] - x[i0]), creep
    )


def main(seeds=SEEDS) -> list[BlindRow]:
    """Run every condition and seed; write results/e2_blind.csv."""
    rows = [
        run(kind, mode, version, seed)
        for kind in KINDS
        for mode in MODES
        for version in VERSIONS
        for seed in seeds
    ]
    write_rows('e2_blind', rows)
    return rows


if __name__ == '__main__':
    main(SEEDS if len(sys.argv) < 2 else tuple(range(1, int(sys.argv[1]) + 1)))
