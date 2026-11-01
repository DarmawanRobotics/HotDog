"""Configuration of cloud_merger_node (the M20's front and rear LiDAR as one cloud)."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_utils.config import param

LEVEL_SOURCES = ('imu', 'none')


@dataclass(frozen=True)
class MergerConfig:
    """Inputs, output, the self filter, the crop and the leveling of the merged cloud."""

    inputs: tuple[str, ...] = param(
        ('/lidar/front/points', '/lidar/rear/points'),
        live=False,
        doc='PointCloud2 topics; the first one triggers each merged cloud',
    )
    input_rpy_deg: tuple[float, ...] = param(
        (0.0, 0.0, 0.0, 0.0, 0.0, 180.0),
        live=False,
        doc='roll, pitch, yaw per input on top of its URDF frame (rear Airy faces backwards)',
    )
    output_topic: str = param('/lidar/points', live=False, doc='merged cloud in the base frame')
    require_all: bool = param(
        True, live=False, doc='publish only while every input is fresh (a blind side stops it)'
    )
    max_age_sec: float = param(
        0.3, min=0.02, max=5.0, unit='s', live=False, doc='an input older than this is stale'
    )
    range_min: float = param(
        0.15, min=0.0, max=5.0, unit='m', live=False, doc='closer to the sensor: dropped'
    )
    range_max: float = param(
        30.0, min=1.0, max=300.0, unit='m', live=False, doc='farther from base_link: dropped'
    )
    height_max: float = param(
        2.5, min=0.1, max=20.0, unit='m', live=False, doc='above the floor: dropped'
    )
    self_margin: float = param(
        0.05, min=0.0, max=1.0, unit='m', live=False, doc='self filter: footprint grown by this'
    )
    self_height: float = param(
        0.6, min=0.0, max=3.0, unit='m', live=False, doc='self filter: top of the body above base'
    )
    stride: int = param(1, min=1, max=64, live=False, doc='keep every n-th point (1: all)')
    level_source: str = param(
        'imu',
        choices=LEVEL_SOURCES,
        live=False,
        doc='imu: remove roll and pitch of the body (perception then trusts a level base)',
    )
    imu_topic: str = param('/m20/imu', live=False, doc='IMU with the body attitude')
    imu_max_age_sec: float = param(
        0.5, min=0.01, max=5.0, unit='s', live=False, doc='older attitude: not leveled'
    )
    max_level_deg: float = param(
        30.0, min=1.0, max=80.0, unit='deg', live=False, doc='larger tilts: not leveled'
    )

    def validate(self) -> list[str]:
        """Return cross-field problems."""
        problems = []
        if not self.inputs:
            problems.append('inputs must name at least one topic')
        if len(self.input_rpy_deg) not in (0, 3 * len(self.inputs)):
            problems.append('input_rpy_deg needs 3 values (roll, pitch, yaw) per input, or none')
        if self.range_min >= self.range_max:
            problems.append('range_min must be below range_max')
        return problems

    def rpy(self, index: int) -> tuple[float, float, float]:
        """Return the extra roll, pitch, yaw (deg) of an input."""
        if not self.input_rpy_deg:
            return (0.0, 0.0, 0.0)
        values = self.input_rpy_deg[3 * index : 3 * index + 3]
        return (float(values[0]), float(values[1]), float(values[2]))
