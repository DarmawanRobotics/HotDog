"""
Perception as lidar_sector_node runs it (v0.2), and the v0.1 rule for blind clouds (baseline).

PerceptionV02 drives dharma_perception's SectorPipeline and adds the node's watchdog: no usable
cloud for input.timeout_sec publishes every sector BLOCKED. PerceptionV01 is the baseline of the
evaluation: a cloud with fewer than 100 raw points gave an all-zero safety scan (which the v0.1
mux read as free) and nothing was published while no cloud arrived.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dharma_perception.core.config import PerceptionConfig
from dharma_perception.core.pipeline import Frame, SectorPipeline
from dharma_perception.core.sectors import SectorLayout
from dharma_utils.math import Pose2D, make_transform
from dharma_utils.robot import RobotProfile

WATCHDOG_EVERY_SEC = 0.1
V01_MIN_RAW_POINTS = 100


@dataclass(frozen=True)
class Published:
    """One pair of sector scans as the node publishes them (robot base frame)."""

    stamp: float
    front: np.ndarray
    safety: np.ndarray
    blocked_reason: str = ''
    front_layout: SectorLayout | None = None
    safety_layout: SectorLayout | None = None


class PerceptionV02:
    """SectorPipeline plus the watchdog of lidar_sector_node."""

    def __init__(self, robot: RobotProfile, config: PerceptionConfig | None = None, mount=None):
        self.config = config or PerceptionConfig()
        self.pipeline = SectorPipeline(self.config, robot)
        self.mount = make_transform(mount if mount is not None else (0.13011, -0.02329, 0.17598))
        self.last_ok = 0.0
        self.next_watchdog = WATCHDOG_EVERY_SEC

    @property
    def front_layout(self):
        """Sector layout of perception/sector_scan."""
        return self.pipeline.front

    @property
    def safety_layout(self):
        """Sector layout of perception/safety_scan."""
        return self.pipeline.safety

    def process(self, stamp: float, points: np.ndarray, odom_base: Pose2D, now: float):
        """Return the scans of one cloud (sensor frame); a usable one feeds the watchdog."""
        frame = Frame(points, self.mount, stamp, None, np.eye(3), odom_base)
        result = self.pipeline.process(frame)
        if not result.blocked_reason:
            self.last_ok = now
        return self.published(stamp, result.front, result.safety, result.blocked_reason)

    def published(self, stamp: float, front, safety, reason: str) -> Published:
        """Return a scan pair with the layouts of this pipeline."""
        p = self.pipeline
        return Published(stamp, front, safety, reason, p.front, p.safety)

    def watchdog(self, now: float) -> Published | None:
        """Return BLOCKED scans while no usable cloud arrived for input.timeout_sec."""
        if now + 1e-9 < self.next_watchdog:
            return None
        self.next_watchdog = now + WATCHDOG_EVERY_SEC
        if now - self.last_ok <= self.config.input.timeout_sec:
            return None
        blocked = self.pipeline.blocked('no usable cloud')
        return self.published(now, blocked.front, blocked.safety, blocked.blocked_reason)


class PerceptionV01(PerceptionV02):
    """Baseline: v0.1 sector scans of a blind cloud (all zero) and no watchdog."""

    def process(self, stamp: float, points: np.ndarray, odom_base: Pose2D, now: float):
        """Return the scans; fewer than 100 raw points give an all-zero safety scan."""
        if len(points) < V01_MIN_RAW_POINTS:
            front = self.pipeline.front.free()  # v0.1 binned nothing: every sector free
            safety = np.zeros(self.pipeline.safety.num_sectors, dtype=np.float32)
            return self.published(stamp, front, safety, 'v0.1 blind: all-zero safety scan')
        return super().process(stamp, points, odom_base, now)

    def watchdog(self, now: float) -> Published | None:
        """v0.1 had no watchdog: a silent LiDAR published nothing."""
        return None
