"""People in a scenario: standing, or walking once the robot passes a trigger line."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

RADIUS = 0.25
HEIGHT = 1.7


@dataclass(frozen=True)
class Person:
    """Starts at (x, y), walks with (vx, vy) once the robot's x passes trigger_x, for walk_sec."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    trigger_x: float = -math.inf
    walk_sec: float = math.inf
    leaves: bool = False  # gone after walking (through a door)


class Crowd:
    """Circles of the people at a time, for Rig.people."""

    def __init__(self, people: list[Person]):
        self.people = people
        self.started: list[float | None] = [None] * len(people)

    def __call__(self, rig, now: float) -> np.ndarray:
        """Return the (N, 4) circles at now."""
        circles = []
        for i, p in enumerate(self.people):
            if self.started[i] is None and rig.pose.x >= p.trigger_x:
                self.started[i] = now
            walked = 0.0 if self.started[i] is None else min(now - self.started[i], p.walk_sec)
            if p.leaves and walked >= p.walk_sec:
                continue
            circles.append((p.x + p.vx * walked, p.y + p.vy * walked, RADIUS, HEIGHT))
        return np.array(circles, dtype=float).reshape(-1, 4)
