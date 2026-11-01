"""Worlds, robot profile and seeds shared by the experiments."""

from __future__ import annotations

from pathlib import Path

from common.stack import roots
from dharma_sim.core.world import World
from dharma_utils.robot import RobotProfile

WORLDS = Path(__file__).resolve().parents[1] / 'worlds'
SEEDS = tuple(range(1, 21))


def robot() -> RobotProfile:
    """Return the default robot profile (robot_bringup/config/robot.yaml has the same values)."""
    return RobotProfile()


def world(name: str) -> World:
    """Load experiments/worlds/<name>.yaml."""
    return World.from_yaml(str(WORLDS / f'{name}.yaml'))


def sim_file(relative: str) -> Path:
    """Return a file of the dharma_sim checkout (config/worlds/..., config/routes/...)."""
    for root in roots():
        path = root / 'dharma_sim' / relative
        if path.is_file():
            return path
    raise FileNotFoundError(relative)
