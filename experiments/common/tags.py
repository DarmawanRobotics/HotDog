"""
Simulated fiducial detections: a forward camera, the tags of the world, noise and outliers.

A tag is detected when it lies in the camera's field of view, faces the camera, is not hidden
by a wall or pillar and is closer than max_range. The detection T_cam_tag gets the noise the
localization assumes (dharma_localization TagNoise: position sigma1 d^2 / cos(view angle) per
axis, heading sigma_psi1 d / cos(view angle) about the vertical); with outlier_rate it is an
outlier instead: a heading error of 5-25 deg and a 0.1-0.4 m position error, like the pose
ambiguity of a small planar tag.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from dharma_localization.core.sources.tag import TagNoise, view_angle
from dharma_sim.core.world import World, cast_rays
from dharma_utils.math import Pose2D, compose, inverse, make_transform, planar_transform

OPTICAL = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])  # cam axes in base


@dataclass(frozen=True)
class Camera:
    """A forward camera in base_link (optical frame: z forward, x right, y down)."""

    xyz: tuple[float, float, float] = (0.30, 0.0, 0.25)
    hfov_deg: float = 69.0
    vfov_deg: float = 42.0
    max_range: float = 6.0
    max_view_angle_deg: float = 75.0

    def base_cam(self) -> np.ndarray:
        """Return T_base_cam (4x4)."""
        m = make_transform(self.xyz)
        m[:3, :3] = OPTICAL
        return m


@dataclass(frozen=True)
class Detection:
    """One tag detection and whether it is a simulated outlier."""

    frame: str
    cam_tag: np.ndarray
    outlier: bool


class TagDetector:
    """Detections of the world's tags from the true robot pose."""

    def __init__(
        self,
        world: World,
        base_height: float,
        rng: np.random.Generator,
        camera: Camera | None = None,
        noise: TagNoise | None = None,
        outlier_rate: float = 0.05,
    ):
        self.world = world
        self.base_height = base_height
        self.rng = rng
        self.camera = camera or Camera()
        self.noise = noise or TagNoise()
        self.outlier_rate = outlier_rate
        self.base_cam = self.camera.base_cam()
        self.tags = {name: make_transform(v[:3], v[3:]) for name, v in world.tags.items()}

    def detect(self, pose: Pose2D) -> list[Detection]:
        """Return the detections at the true pose."""
        map_base = planar_transform(pose.x, pose.y, pose.yaw, self.base_height)
        map_cam = compose(map_base, self.base_cam)
        out = []
        for name, map_tag in self.tags.items():
            cam_tag = compose(inverse(map_cam), map_tag)
            if self.visible(cam_tag, map_cam, map_tag):
                out.append(self.noisy(name, cam_tag))
        return out

    def visible(self, cam_tag: np.ndarray, map_cam: np.ndarray, map_tag: np.ndarray) -> bool:
        """Return True when the camera sees the tag."""
        cam = self.camera
        x, y, z = cam_tag[:3, 3]
        if z <= 0.1 or math.hypot(x, y, z) > cam.max_range:
            return False
        if abs(math.atan2(x, z)) > math.radians(cam.hfov_deg) / 2.0:
            return False
        if abs(math.atan2(y, z)) > math.radians(cam.vfov_deg) / 2.0:
            return False
        if float(np.dot(cam_tag[:3, 2], -cam_tag[:3, 3])) <= 0.0:
            return False  # the plate faces away
        if view_angle(cam_tag) > math.radians(cam.max_view_angle_deg):
            return False
        return not self.hidden(map_cam, map_tag)

    def hidden(self, map_cam: np.ndarray, map_tag: np.ndarray) -> bool:
        """Return True when a wall or pillar lies between the camera and the tag (2D)."""
        c, t = map_cam[:2, 3], map_tag[:2, 3]
        distance = float(np.hypot(*(t - c)))
        angle = math.atan2(t[1] - c[1], t[0] - c[0])
        nearest = float(cast_rays(self.world, c[0], c[1], np.array([angle]), distance + 1.0)[0])
        return nearest < distance - 0.05

    def noisy(self, name: str, cam_tag: np.ndarray) -> Detection:
        """Return the detection with noise, or an outlier."""
        distance = float(np.linalg.norm(cam_tag[:3, 3]))
        oblique = 1.0 / max(math.cos(view_angle(cam_tag)), 0.1)
        sigma_p = self.noise.sigma_xy_at_1m * distance**2 * oblique
        sigma_yaw = self.noise.sigma_yaw_at_1m * distance * oblique
        outlier = bool(self.rng.random() < self.outlier_rate)
        if outlier:
            yaw = math.radians(self.rng.uniform(5.0, 25.0)) * self.rng.choice((-1.0, 1.0))
            direction = self.rng.uniform(0.0, 2.0 * math.pi)
            shift = self.rng.uniform(0.1, 0.4) * np.array([math.cos(direction), 0.0,
                                                          math.sin(direction)])  # fmt: skip
        else:
            yaw = float(self.rng.normal(0.0, sigma_yaw))
            shift = self.rng.normal(0.0, sigma_p, 3)
        c, s = math.cos(yaw), math.sin(yaw)
        about_y = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])
        out = cam_tag.copy()
        out[:3, :3] = about_y @ cam_tag[:3, :3]
        out[:3, 3] = cam_tag[:3, 3] + shift
        return Detection(name, out, outlier)
