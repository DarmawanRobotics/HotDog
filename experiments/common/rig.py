"""
Closed loop of the pure cores at the node rates: simulator, perception, control mux, a driver.

One clock in ticks of 10 ms: physics at 100 Hz, LiDAR, perception and its watchdog at 10 Hz,
the driver (follower or a command stream) at 20 Hz and the mux watchdog at 50 Hz, with phases
drawn from the seed. Every message is delivered when it is published (no transport delay);
the sensor and command latencies of the simulator apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Callable  # subscripted at runtime below (Python 3.8)

import numpy as np

from common.metrics import box_clearance
from common.mux import MuxV02
from common.perception import PerceptionV02, Published
from dharma_sim.core.body import Twist
from dharma_sim.core.config import SimConfig
from dharma_sim.core.scenario import Scenario
from dharma_sim.core.simulation import Simulation
from dharma_sim.core.world import World
from dharma_utils.math import Pose2D, default_rng
from dharma_utils.robot import RobotProfile

TICK_SEC = 0.01
LIDAR_EVERY = 10
DRIVER_EVERY = 5
MUX_EVERY = 2


@dataclass
class Trace:
    """What happened, sampled at the physics rate and at every mux output."""

    t: list = field(default_factory=list)
    pose: list = field(default_factory=list)
    twist: list = field(default_factory=list)
    clearance: list = field(default_factory=list)
    cmd_t: list = field(default_factory=list)
    cmd: list = field(default_factory=list)
    scans: list = field(default_factory=list)  # (receive time, blocked sectors, field input)

    def arrays(self) -> dict:
        """Return the samples as numpy arrays."""
        return {
            't': np.asarray(self.t),
            'pose': np.asarray(self.pose).reshape(-1, 3),
            'twist': np.asarray(self.twist).reshape(-1, 3),
            'clearance': np.asarray(self.clearance),
            'cmd_t': np.asarray(self.cmd_t),
            'cmd': np.asarray(self.cmd).reshape(-1, 3),
        }


Driver = Callable[['Rig', float], 'tuple[float, float, float] | None']
People = Callable[['Rig', float], np.ndarray]
ScanFilter = Callable[[float, np.ndarray], 'np.ndarray | None']


class Rig:
    """Simulated robot, perception and mux in a loop; a driver sends commands at 20 Hz."""

    def __init__(
        self,
        world: World,
        robot: RobotProfile,
        seed: int,
        scenario: Scenario | None = None,
        sim_config: SimConfig | None = None,
        perception=None,
        mux=None,
    ):
        self.robot = robot
        self.seed = seed
        self.sim = Simulation(sim_config or SimConfig(seed=seed), robot, world, scenario)
        self.perception = perception or PerceptionV02(robot)
        self.mux = mux or MuxV02(robot)
        rng = default_rng([seed, 7])
        self.phase = {
            'lidar': int(rng.integers(LIDAR_EVERY)),
            'driver': int(rng.integers(DRIVER_EVERY)),
            'mux': int(rng.integers(MUX_EVERY)),
        }
        self.driver: Driver | None = None
        self.source = 'navigation'
        self.people: People | None = None
        self.scan_filter: ScanFilter | None = None
        self.listeners: list[Callable[[Published, float], None]] = []
        self.trace = Trace()
        self.tick = 0

    @property
    def now(self) -> float:
        """Return the current time (s)."""
        return self.tick * TICK_SEC

    @property
    def pose(self) -> Pose2D:
        """Return the true pose."""
        return self.sim.body.pose

    def run(self, until: float, stop: Callable[[Rig], bool] | None = None):
        """Advance until the time (s) or until stop(rig) is True."""
        while self.now < until - 1e-9:
            self.tick += 1
            self.step()
            if stop is not None and stop(self):
                return

    def step(self):
        """One tick of 10 ms."""
        now, k = self.now, self.tick
        if self.people is not None:
            self.sim.dynamic = self.people(self, now)
        self.sim.step(now)
        self.record(now)
        if (k - self.phase['lidar']) % LIDAR_EVERY == 0:
            self.sense(now)
        if (k - self.phase['mux']) % MUX_EVERY == 0 and self.mux.tick(now):
            self.send(now, (0.0, 0.0, 0.0))
        if self.driver is not None and (k - self.phase['driver']) % DRIVER_EVERY == 0:
            command = self.driver(self, now)
            if command is not None:
                out = self.mux.forward(self.source, command, now)
                if out is not None:
                    self.send(now, out)

    def sense(self, now: float):
        """LiDAR scan, perception and its watchdog, delivery of the scans."""
        sample = self.sim.scan(now)
        published = []
        if sample is not None:
            points = sample.points
            if self.scan_filter is not None:
                points = self.scan_filter(now, points)
            if points is not None:
                odom = self.sim.odom.at(sample.stamp) or Pose2D()
                published.append(self.perception.process(sample.stamp, points, odom, now))
        watchdog = self.perception.watchdog(now)
        if watchdog is not None:
            published.append(watchdog)
        for scan in published:
            self.mux.update_scan(scan, now)
            self.trace.scans.append((now, int(np.sum(scan.safety <= 0.0)), scan.blocked_reason))
            for listener in self.listeners:
                listener(scan, now)

    def send(self, now: float, command: tuple[float, float, float]):
        """Deliver a mux output to the simulated robot driver."""
        self.sim.command(now, Twist(*command))
        self.trace.cmd_t.append(now)
        self.trace.cmd.append(command)

    def record(self, now: float):
        """Sample the true state."""
        body = self.sim.body
        self.trace.t.append(now)
        self.trace.pose.append((body.pose.x, body.pose.y, body.pose.yaw))
        self.trace.twist.append((body.twist.vx, body.twist.vy, body.twist.wz))
        circles = self.sim.obstacles(now)
        clearance = box_clearance(self.robot.footprint, body.pose, circles)
        self.trace.clearance.append(clearance)


def speed_of(twist: np.ndarray) -> np.ndarray:
    """Return the linear speed of (N, 3) twists."""
    return np.hypot(twist[:, 0], twist[:, 1])


def fastest_point(twist: np.ndarray, radius: float) -> np.ndarray:
    """Return the speed of the fastest point of the body (linear + |wz| r_circumscribed)."""
    return speed_of(twist) + np.abs(twist[:, 2]) * radius


def first_after(times: np.ndarray, mask: np.ndarray, t0: float) -> float:
    """Return the first time >= t0 where mask is True (inf: never)."""
    idx = np.flatnonzero((times >= t0 - 1e-9) & mask)
    return float(times[idx[0]]) if len(idx) else math.inf
