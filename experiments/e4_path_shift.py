"""
E4: a corridor with standing and walking people; path shift, reactive avoidance, none.

Reactive avoidance is the VFH policy of the bringup. The follower drives a 20 m route along
the centre of a 3 m corridor (full rig: perception, follower, avoidance node, mux with its
protective field). Per seed: a person stands on the
route at 5-6.5 m, one beside it at 10-11.5 m, one walks the same way at 0.2 m/s from 13-14 m
(once the robot passes 9 m) and one crosses at 17-18 m at 0.6 m/s (once the robot is 3 m
before) and leaves. Layout beside_route puts both standing people 0.6-0.9 m beside the route,
on opposite sides. Measured: smallest clearance between the footprint and a person, time to
the goal (150 s limit), stops (speed below 0.05 m/s after above 0.15 m/s, before the goal) and
the largest distance from the route.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import sys

import common  # noqa: F401  (puts the stack on sys.path)
from common.metrics import write_rows
from common.navigation import FollowerDriver, follower_config
from common.people import Crowd, Person
from common.rig import Rig, speed_of
from common.worlds import SEEDS, robot, world
import numpy as np

from dharma_navigation.core.follower.state import FollowerState
from dharma_utils.io import RoutePoint
from dharma_utils.math import default_rng

MODES = ('path_shift', 'reactive', 'off')
LAYOUTS = ('on_route', 'beside_route')
GOAL_X = 20.0
TIMEOUT_SEC = 150.0
GIVE_UP_SEC = 20.0  # BLOCKED this long: over (the planner's replanning is not in the loop)
START_SEC = 1.0


@dataclass(frozen=True)
class CorridorRow:
    """One E4 run."""

    layout: str
    mode: str
    seed: int
    completed: bool
    time_sec: float
    stops: int
    min_clearance_m: float
    max_offset_m: float
    collided: bool
    final_state: str


def route() -> list[RoutePoint]:
    """Return the corridor route: every 0.2 m along y = 0 up to the goal."""
    xs = np.arange(0.0, GOAL_X + 1e-9, 0.2)
    return [RoutePoint(float(x), 0.0, 0.0, 0.0) for x in xs]


def crowd(seed: int, layout: str = 'on_route') -> Crowd:
    """Return the people of a seed: on_route, or beside_route (no one standing on it)."""
    rng = default_rng([seed, 4])
    u = rng.uniform
    standing, beside = (u(5.0, 6.5), u(-0.3, 0.3)), (u(10.0, 11.5), u(-0.7, 0.7))
    if layout == 'beside_route':
        side = rng.choice((-1.0, 1.0))
        standing = (standing[0], side * u(0.6, 0.9))
        beside = (beside[0], -side * u(0.6, 0.9))
    walking, xc = (u(13.0, 14.0), u(-0.4, 0.4)), u(17.0, 18.0)
    return Crowd([
        Person(*standing),
        Person(*beside),
        Person(*walking, vx=0.2, trigger_x=9.0, walk_sec=50.0),
        Person(xc, -1.2, vy=0.6, trigger_x=xc - 3.0, walk_sec=4.0, leaves=True),
    ])  # fmt: skip


def count_stops(t: np.ndarray, x: np.ndarray, speed: np.ndarray, until: float) -> int:
    """Return how often the speed fell below 0.05 m/s after exceeding 0.15 m/s (x < until)."""
    stops, moving = 0, False
    for ti, xi, v in zip(t, x, speed):  # columns of one trace
        if xi >= until or ti < START_SEC:
            continue
        if v > 0.15:
            moving = True
        elif v < 0.05 and moving:
            stops, moving = stops + 1, False
    return stops


def finished(driver: FollowerDriver):
    """Return the stop condition of a run: goal reached or BLOCKED for GIVE_UP_SEC."""
    since = [None]

    def stop(rig: Rig) -> bool:
        state = driver.state
        if state is not FollowerState.BLOCKED:
            since[0] = None
        elif since[0] is None:
            since[0] = rig.now
        return state is FollowerState.GOAL_REACHED or (
            since[0] is not None and rig.now - since[0] >= GIVE_UP_SEC
        )

    return stop


def run(mode: str, seed: int, layout: str = 'on_route') -> CorridorRow:
    """Run one corridor and measure it."""
    rig = Rig(world('corridor'), robot(), seed)
    rig.people = crowd(seed, layout)
    driver = FollowerDriver(rig, route(), follower_config(avoidance_mode=mode), START_SEC)
    rig.driver = driver
    rig.run(TIMEOUT_SEC, finished(driver))
    data = rig.trace.arrays()
    t, pose = data['t'], data['pose']
    done = driver.state is FollowerState.GOAL_REACHED
    along = (pose[:, 0] > 0.5) & (pose[:, 0] < GOAL_X - 0.5)
    speed = speed_of(data['twist'])
    return CorridorRow(
        layout, mode, seed, done, rig.now - START_SEC if done else math.nan,
        count_stops(t, pose[:, 0], speed, GOAL_X - 0.6), float(data['clearance'].min()),
        float(np.abs(pose[along, 1]).max()), bool(rig.sim.body.collided), driver.state.name,
    )  # fmt: skip


def main(seeds=SEEDS) -> list[CorridorRow]:
    """Run every mode and seed; write results/e4_path_shift.csv."""
    rows = [run(m, s, layout) for layout in LAYOUTS for m in MODES for s in seeds]
    write_rows('e4_path_shift', rows)
    return rows


if __name__ == '__main__':
    main(SEEDS if len(sys.argv) < 2 else tuple(range(1, int(sys.argv[1]) + 1)))
