"""
The M20's two LiDARs as one cloud in base_link: transform, self filter, crop, leveling.

Every input cloud is moved into the base frame when it arrives (its URDF transform and an
optional extra rotation); a merged cloud goes out when the trigger input (the first) arrives
and, with require_all, only while every other input is fresh. A stale side therefore stops the
output and perception publishes its scans BLOCKED (fail safe) instead of a half-blind scan.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from dharma_utils.math import compose, make_transform, quat_from_rpy, quat_to_matrix
from dharma_utils.robot import RobotProfile
from hotdog_base.core.config import MergerConfig


@dataclass
class Part:
    """The latest cloud of one input, already in the base frame."""

    points: np.ndarray
    stamp: float  # header stamp, s
    received: float  # monotonic receive time, s


def extra_rotation(rpy_deg: tuple[float, float, float]) -> np.ndarray:
    """Return the 4x4 rotation of an input on top of its URDF frame."""
    roll, pitch, yaw = (math.radians(v) for v in rpy_deg)
    return make_transform(quat=quat_from_rpy(roll, pitch, yaw))


def level_rotation(quat, max_deg: float) -> np.ndarray | None:
    """Return the 3x3 rotation removing roll and pitch of the body, None when implausible."""
    r = quat_to_matrix(quat)
    yaw = math.atan2(r[1, 0], r[0, 0])
    c, s = math.cos(-yaw), math.sin(-yaw)
    level = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]) @ r
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(level[2, 2])))))
    return level if tilt <= max_deg else None


class CloudMerger:
    """Keeps the latest cloud of each input and merges them on the trigger input."""

    def __init__(self, config: MergerConfig, robot: RobotProfile):
        self.config = config
        self.robot = robot
        self.parts: dict[int, Part] = {}
        self.extras = [extra_rotation(config.rpy(i)) for i in range(len(config.inputs))]
        fp = robot.footprint
        m = config.self_margin
        self.body = (fp.front + m, -(fp.rear + m), fp.half_width + m)

    def to_base(self, index: int, points: np.ndarray, sensor_to_base: np.ndarray) -> np.ndarray:
        """Return sensor points in the base frame, near ones and the stride dropped."""
        pts = np.asarray(points, dtype=np.float32)[:: self.config.stride]
        if len(pts):
            near = np.einsum('ij,ij->i', pts, pts) < self.config.range_min**2
            pts = pts[~near]
        m = compose(sensor_to_base, self.extras[index])
        return (pts @ m[:3, :3].T.astype(np.float32) + m[:3, 3].astype(np.float32)).astype(
            np.float32
        )

    def update(self, index: int, points: np.ndarray, stamp: float, now: float):
        """Keep the latest base-frame cloud of an input."""
        self.parts[index] = Part(points, stamp, now)

    def stale(self, now: float) -> list[int]:
        """Return the inputs without a fresh cloud."""
        limit = self.config.max_age_sec
        return [
            i
            for i in range(len(self.config.inputs))
            if i not in self.parts or now - self.parts[i].received > limit
        ]

    def merge(self, now: float, level: np.ndarray | None = None):
        """Return (points, stamp) of the fresh inputs, or None when an input is missing."""
        stale = self.stale(now)
        if 0 in stale or (self.config.require_all and stale):
            return None
        fresh = [self.parts[i] for i in sorted(self.parts) if i not in stale]
        points = np.concatenate([p.points for p in fresh]) if fresh else np.empty((0, 3))
        if level is not None and len(points):
            points = points @ level.T.astype(np.float32)
        return self.crop(points.astype(np.float32)), max(p.stamp for p in fresh)

    def crop(self, points: np.ndarray) -> np.ndarray:
        """Drop the robot's own body, points too far and points too high above the floor."""
        if not len(points):
            return points
        x, y, z = points[:, 0], points[:, 1], points[:, 2]
        front, rear, half = self.body
        floor = -self.robot.base_height
        body = (x < front) & (x > rear) & (np.abs(y) < half)
        body &= (z > floor) & (z < self.config.self_height)
        far = x * x + y * y > self.config.range_max**2
        high = z > floor + self.config.height_max
        return points[~(body | far | high)]
