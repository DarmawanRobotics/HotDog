"""
E1: stopping distance of the protective field against the braking model D(v).

AUTO, a constant command stream at the follower rate (20 Hz) through the control mux. Once the
robot cruises at v, a person (circle r = 0.25 m, 1.7 m high) appears on its axis, D(v) + m in
front of the front edge (m = field.margin): the nearest appearance from which the model still
promises a stop with the margin. Measured: the distance travelled from the first safety scan
that shows the person to standstill, the smallest clearance of the footprint and the reaction
time (appearance to the first braking of the body, against the model's t_r). Twice: with the
field's default human_speed (0.5 m/s, ISO/TS 15066 separation: the field also keeps the distance
a person walking toward the robot covers until it stands) and with human_speed 0 (the braking
model alone).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import sys

import common  # noqa: F401  (puts the stack on sys.path)
from common.metrics import write_rows
from common.mux import MuxV02
from common.rig import Rig, first_after, speed_of
from common.worlds import SEEDS, robot, world
import numpy as np

from dharma_control.core.config import FieldConfig
from dharma_utils.math import default_rng
from dharma_utils.safety import stopping_distance

SPEEDS = (0.2, 0.4, 0.6, 0.8)
HUMAN_SPEEDS = (FieldConfig().human_speed, 0.0)
RADIUS = 0.25
HEIGHT = 1.7
START_SEC = 1.0


@dataclass(frozen=True)
class StopRow:
    """One E1 run."""

    speed: float
    human_speed: float
    seed: int
    model_m: float
    appear_m: float
    seen_after_sec: float
    reaction_sec: float
    travel_m: float
    travel_from_appear_m: float
    min_clearance_m: float
    collided: bool


class Appearing:
    """A person that appears at a clearance once the robot cruises (after a seeded delay)."""

    def __init__(self, speed: float, clearance: float, delay: float):
        self.speed, self.clearance, self.delay = speed, clearance, delay
        self.cruising_at: float | None = None
        self.circle: np.ndarray | None = None
        self.appeared_at = math.inf

    def __call__(self, rig: Rig, now: float) -> np.ndarray:
        """Return the circles at now."""
        if self.circle is None:
            if self.cruising_at is None and rig.sim.body.twist.vx >= self.speed - 1e-6:
                self.cruising_at = now
            if self.cruising_at is not None and now >= self.cruising_at + self.delay:
                pose, front = rig.pose, rig.robot.footprint.front
                ahead = front + self.clearance + RADIUS
                x, y = pose.apply(np.array([[ahead, 0.0]]))[0]
                self.circle = np.array([[x, y, RADIUS, HEIGHT]])
                self.appeared_at = now
        return self.circle if self.circle is not None else np.empty((0, 4))


def shows(scan, person: Appearing, profile) -> bool:
    """Return True when the safety scan has a return of the person (sectors ahead)."""
    layout = scan.safety_layout
    angles = layout.angle_min + (np.arange(layout.num_sectors) + 0.5) * layout.increment
    reach = profile.footprint.front + person.clearance + 2.0 * RADIUS + 0.2
    ahead = np.abs(angles) < math.radians(20.0)
    return bool(np.any(ahead & (scan.safety > 0.0) & (scan.safety < reach)))


def run(speed: float, seed: int, human_speed: float = HUMAN_SPEEDS[0]) -> StopRow:
    """Run one stop with the field's assumed human speed (m/s) and measure it."""
    profile = robot()
    margin = FieldConfig().margin
    model = stopping_distance(speed, profile.limits.max_decel, profile.limits.reaction_time)
    rng = default_rng([seed, 1])
    person = Appearing(speed, model + margin, float(rng.uniform(0.0, 0.1)))
    field = replace(FieldConfig(), human_speed=human_speed)
    rig = Rig(world('hall'), profile, seed, mux=MuxV02(profile, field=field))
    rig.people = person
    rig.driver = lambda r, now: (speed, 0.0, 0.0) if now >= START_SEC else None
    seen = []

    def on_scan(scan, now):
        if now >= person.appeared_at and not seen and shows(scan, person, profile):
            seen.append(now)

    rig.listeners.append(on_scan)

    def stopped(r: Rig) -> bool:
        return bool(seen) and r.now > seen[0] + 0.5 and r.sim.body.twist.vx <= 0.0

    rig.run(20.0, stopped)
    data = rig.trace.arrays()
    t, x = data['t'], data['pose'][:, 0]
    t_seen = seen[0] if seen else math.inf
    t_stop = first_after(t, speed_of(data['twist']) <= 1e-9, t_seen)
    t_brake = first_after(t, data['twist'][:, 0] < speed - 1e-6, person.appeared_at)
    at = {name: int(np.searchsorted(t, v)) for name, v in
          (('seen', t_seen), ('stop', t_stop), ('appear', person.appeared_at))}  # fmt: skip
    after = t >= person.appeared_at
    return StopRow(
        speed, human_speed, seed, model, model + margin, t_seen - person.appeared_at,
        t_brake - person.appeared_at,
        float(x[min(at['stop'], len(x) - 1)] - x[min(at['seen'], len(x) - 1)]),
        float(x[min(at['stop'], len(x) - 1)] - x[min(at['appear'], len(x) - 1)]),
        float(data['clearance'][after].min()), bool(rig.sim.body.collided),
    )  # fmt: skip


def main(seeds=SEEDS) -> list[StopRow]:
    """Run every speed and seed; write results/e1_stopping.csv."""
    rows = [run(v, s, h) for h in HUMAN_SPEEDS for v in SPEEDS for s in seeds]
    write_rows('e1_stopping', rows)
    return rows


if __name__ == '__main__':
    main(SEEDS if len(sys.argv) < 2 else tuple(range(1, int(sys.argv[1]) + 1)))
