"""
E5: backing up after the inspection at a stop point that faces a wall.

The follower drives a 5.5 m route north, 0.9 m from the east wall of a room (full rig: 360 deg
front and safety scans, path shift, the mux). Its stop point in the middle faces the wall
(yaw 0, 0.5 m between the front edge and the wall) for a 5 s dwell. Conditions: none (no
back-up, inspection.reverse_distance_m 0: the robot turns in place and goes on), free (backs up
1 m, then rejoins the route 1 m past the stop) and person (the same while a person stands behind
the robot, 0.5-1.5 m from its rear edge, who stepped in during the dwell). Nothing gives up on
BLOCKED (a loaded route has no replanning: the follower waits, a join gives up after
join.timeout_sec). Measured: completion and time (120 s limit), how far the robot backed up,
how long it reported BLOCKED, the smallest clearance to the person and to the walls after the
dwell.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import sys

import common  # noqa: F401  (puts the stack on sys.path)
from common.metrics import box_clearance, write_rows
from common.navigation import FollowerDriver, follower_config
from common.people import HEIGHT, RADIUS
from common.perception import PerceptionV02
from common.rig import Rig
from common.worlds import SEEDS, robot, world
import numpy as np

from dharma_navigation.core.config.follower import InspectionConfig
from dharma_navigation.core.follower.state import FollowerState
from dharma_perception.core.config import PerceptionConfig
from dharma_utils.io import RoutePoint
from dharma_utils.math import Pose2D, default_rng

CONDITIONS = ('none', 'free', 'person')
REVERSE_M = 1.0
ROUTE_X = 4.7
STOP_Y = 0.0
DWELL_SEC = 5.0
START_SEC = 1.0
TIMEOUT_SEC = 120.0
WALL_STEP_M = 0.02


@dataclass(frozen=True)
class BackupRow:
    """One E5 run."""

    condition: str
    seed: int
    completed: bool
    time_sec: float
    backed_m: float
    blocked_sec: float
    person_gap_m: float
    person_clearance_m: float
    wall_clearance_m: float
    collided: bool
    final_state: str


def route() -> list[RoutePoint]:
    """Return the route: every 0.2 m north along x = ROUTE_X, the stop point facing east."""
    ys = np.arange(-2.5, 3.0 + 1e-9, 0.25)
    north = math.pi / 2.0
    points = [RoutePoint(ROUTE_X, float(y), north, 0.0) for y in ys if abs(y - STOP_Y) > 1e-6]
    points.append(RoutePoint(ROUTE_X, STOP_Y, 0.0, DWELL_SEC))
    return sorted(points, key=lambda p: p.y)


class StepsIn:
    """A person who steps in behind the robot during its dwell and stands there."""

    def __init__(self, driver: FollowerDriver, gap: float, delay: float):
        self.driver, self.gap, self.delay = driver, gap, delay
        self.dwelling_at: float | None = None
        self.circle = np.empty((0, 4))

    def __call__(self, rig: Rig, now: float) -> np.ndarray:
        """Return the circles at now."""
        if not len(self.circle):
            if self.dwelling_at is None and self.driver.state is FollowerState.DWELLING:
                self.dwelling_at = now
            if self.dwelling_at is not None and now >= self.dwelling_at + self.delay:
                pose, rear = rig.pose, rig.robot.footprint.rear
                x, y = pose.apply(np.array([[-(rear + self.gap + RADIUS), 0.0]]))[0]
                self.circle = np.array([[x, y, RADIUS, HEIGHT]])
        return self.circle


def wall_points(rig: Rig) -> np.ndarray:
    """Return the walls of the world sampled every WALL_STEP_M as circles of radius 0."""
    out = []
    for x0, y0, x1, y1, _ in rig.sim.world.segments:
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / WALL_STEP_M) + 1)
        t = np.linspace(0.0, 1.0, n)
        out.append(np.column_stack((x0 + t * (x1 - x0), y0 + t * (y1 - y0))))
    xy = np.vstack(out)
    return np.column_stack((xy, np.zeros(len(xy)), np.ones(len(xy))))


def build(condition: str, seed: int):
    """Return the rig, its driver and the person (None without one)."""
    profile = robot()
    perception = PerceptionConfig()
    perception = replace(perception, front=replace(perception.front, fov_deg=360.0))
    rig = Rig(world('inspection'), profile, seed, perception=PerceptionV02(profile, perception))
    reverse = 0.0 if condition == 'none' else REVERSE_M
    config = follower_config(inspection=InspectionConfig(reverse_distance_m=reverse))
    driver = FollowerDriver(rig, route(), config, START_SEC)
    rig.driver = driver
    person = None
    if condition == 'person':
        rng = default_rng([seed, 5])
        person = StepsIn(driver, float(rng.uniform(0.5, 1.5)), float(rng.uniform(0.0, 2.0)))
        rig.people = person
    return rig, driver, person


def run(condition: str, seed: int) -> BackupRow:
    """Run one stop and measure it."""
    rig, driver, person = build(condition, seed)
    rig.run(TIMEOUT_SEC, lambda r: driver.state is FollowerState.GOAL_REACHED)
    data = rig.trace.arrays()
    t, pose = data['t'], data['pose']
    left = [at for at, state in driver.states if state is FollowerState.DWELLING]
    after = t >= (left[-1] if left else math.inf)
    backed = float(ROUTE_X - pose[after, 0].min()) if after.any() else math.nan
    walls = wall_points(rig)
    fp = rig.robot.footprint
    wall = [box_clearance(fp, Pose2D(*p), walls) for p in pose[after][::10]]
    done = driver.state is FollowerState.GOAL_REACHED
    blocked = sum(state is FollowerState.BLOCKED for _, state in driver.states)
    tick = 1.0 / driver.config.control_rate
    return BackupRow(
        condition, seed, done, rig.now - START_SEC if done else math.nan, backed, blocked * tick,
        person.gap if person else math.nan,
        float(data['clearance'][after].min()) if after.any() else math.nan,
        min(wall) if wall else math.nan, bool(rig.sim.body.collided), driver.state.name,
    )  # fmt: skip


def main(seeds=SEEDS) -> list[BackupRow]:
    """Run every condition and seed; write results/e5_backup.csv."""
    rows = [run(c, s) for c in CONDITIONS for s in seeds]
    write_rows('e5_backup', rows)
    return rows


if __name__ == '__main__':
    main(SEEDS if len(sys.argv) < 2 else tuple(range(1, int(sys.argv[1]) + 1)))
