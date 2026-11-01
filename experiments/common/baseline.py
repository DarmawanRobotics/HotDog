"""
Baseline of E3: the v0.1 localization rule, re-implemented here for the comparison.

Every usable tag detection replaces map->odom with the one that puts the robot on the tag's
map->base (flattened to x, y, yaw), unless map->odom itself would change by more than 0.5 m
or 15 deg (v0.1 max_correction_m / max_correction_deg). No uncertainty is kept.
"""

from __future__ import annotations

import math

import numpy as np

from dharma_localization.core.sources.tag import map_base_from_tag
from dharma_utils.math import Pose2D, angle_diff

MAX_CORRECTION_M = 0.5
MAX_CORRECTION_RAD = math.radians(15.0)


class HardReplace:
    """map->odom replaced by every plausible tag (v0.1)."""

    def __init__(self, start: Pose2D, odom_base: Pose2D):
        self.map_odom = start @ odom_base.inverse()
        self.odom_base = odom_base

    def track(self, odom_base: Pose2D):
        """Follow odometry."""
        self.odom_base = odom_base

    def on_tag(self, map_tag: np.ndarray, base_cam: np.ndarray, cam_tag: np.ndarray) -> bool:
        """Apply one detection; return True when it replaced map->odom."""
        map_base = Pose2D.from_matrix(map_base_from_tag(map_tag, base_cam, cam_tag))
        candidate = map_base @ self.odom_base.inverse()
        moved = math.hypot(candidate.x - self.map_odom.x, candidate.y - self.map_odom.y)
        turned = abs(angle_diff(candidate.yaw, self.map_odom.yaw))
        if moved > MAX_CORRECTION_M or turned > MAX_CORRECTION_RAD:
            return False
        self.map_odom = candidate
        return True

    def base_pose(self) -> Pose2D:
        """Return map->base."""
        return self.map_odom @ self.odom_base
