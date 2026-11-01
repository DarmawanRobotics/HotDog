"""CloudMerger: frames, the self filter, the crop, staleness and leveling."""

from __future__ import annotations

import dataclasses
import math

from hotdog_base.core.config import MergerConfig
from hotdog_base.core.merge import CloudMerger, level_rotation
import numpy as np
import pytest

from dharma_utils.config import ConfigError, build
from dharma_utils.math import make_transform, quat_from_rpy
from dharma_utils.robot import RobotProfile

FRONT = make_transform((0.32, 0.0, -0.013))
REAR = make_transform((-0.32, 0.0, -0.013))


def merger(**changes) -> CloudMerger:
    """Return a merger for the M20 with config changes."""
    config = dataclasses.replace(MergerConfig(), **changes)
    robot = dataclasses.replace(RobotProfile(), base_height=0.42)
    return CloudMerger(config, robot)


def test_default_config_is_valid():
    assert build(MergerConfig, {}) == MergerConfig()


def test_rpy_needs_three_values_per_input():
    with pytest.raises(ConfigError, match='input_rpy_deg'):
        build(MergerConfig, {'input_rpy_deg': [0.0, 0.0]})


def test_front_point_lands_ahead_and_rear_point_behind():
    m = merger()
    ahead = m.to_base(0, np.array([[2.0, 0.0, 0.0]]), FRONT)
    behind = m.to_base(1, np.array([[2.0, 0.0, 0.0]]), REAR)  # rear Airy: yaw 180
    assert ahead[0] == pytest.approx([2.32, 0.0, -0.013], abs=1e-5)
    assert behind[0] == pytest.approx([-2.32, 0.0, -0.013], abs=1e-5)


def test_near_points_and_stride_are_dropped():
    m = merger(stride=2)
    pts = np.array([[0.05, 0.0, 0.0], [5.0, 0, 0], [6.0, 0, 0], [7.0, 0, 0]])
    out = m.to_base(0, pts, np.eye(4))
    assert out[:, 0].tolist() == pytest.approx([6.0])


def test_merge_waits_for_every_input():
    m = merger()
    m.update(0, np.array([[3.0, 0.0, 0.0]], dtype=np.float32), 10.0, now=1.0)
    assert m.merge(1.0) is None
    assert m.stale(1.0) == [1]
    m.update(1, np.array([[-3.0, 0.0, 0.0]], dtype=np.float32), 10.1, now=1.0)
    points, stamp = m.merge(1.05)
    assert len(points) == 2
    assert stamp == pytest.approx(10.1)


def test_stale_side_stops_the_output_unless_allowed():
    m = merger()
    m.update(1, np.array([[-3.0, 0.0, 0.0]]), 9.0, now=0.0)
    m.update(0, np.array([[3.0, 0.0, 0.0]]), 10.0, now=1.0)
    assert m.merge(1.0) is None
    partial = merger(require_all=False)
    partial.update(1, np.array([[-3.0, 0.0, 0.0]]), 9.0, now=0.0)
    partial.update(0, np.array([[3.0, 0.0, 0.0]]), 10.0, now=1.0)
    points, _ = partial.merge(1.0)
    assert points.tolist() == [[3.0, 0.0, 0.0]]


def test_trigger_input_stale_never_publishes():
    m = merger(require_all=False)
    m.update(0, np.array([[3.0, 0.0, 0.0]]), 10.0, now=0.0)
    m.update(1, np.array([[-3.0, 0.0, 0.0]]), 10.0, now=1.0)
    assert m.merge(1.0) is None


def test_crop_drops_body_far_and_high_points():
    m = merger()
    pts = np.array(
        [
            [0.1, 0.1, 0.0],  # inside the body
            [0.1, 0.1, 0.9],  # above the body: kept
            [40.0, 0.0, 0.0],  # beyond range_max
            [3.0, 0.0, 2.5],  # above height_max over the floor
            [3.0, 0.0, -0.3],  # obstacle near the floor
        ],
        dtype=np.float32,
    )
    out = m.crop(pts)
    np.testing.assert_allclose(out, [[0.1, 0.1, 0.9], [3.0, 0.0, -0.3]], atol=1e-6)


def test_level_removes_pitch_but_keeps_yaw_free():
    pitch = math.radians(10.0)
    rot = level_rotation(quat_from_rpy(0.0, pitch, math.radians(90.0)), max_deg=30.0)
    point = np.array([1.0, 0.0, 0.0])  # 1 m ahead in the pitched body
    level = rot @ point
    assert level[2] == pytest.approx(-math.sin(pitch), abs=1e-6)
    assert level[0] == pytest.approx(math.cos(pitch), abs=1e-6)
    assert level[1] == pytest.approx(0.0, abs=1e-6)


def test_level_refuses_implausible_tilt():
    assert level_rotation(quat_from_rpy(math.radians(45.0), 0.0, 0.0), max_deg=30.0) is None


def test_merge_applies_the_level():
    m = merger()
    pitch = math.radians(5.0)
    rot = level_rotation(quat_from_rpy(0.0, pitch, 0.0), max_deg=30.0)
    m.update(0, np.array([[4.0, 0.0, 0.0]], dtype=np.float32), 1.0, now=1.0)
    m.update(1, np.array([[-4.0, 0.0, 0.0]], dtype=np.float32), 1.0, now=1.0)
    points, _ = m.merge(1.0, rot)
    assert points[0, 2] == pytest.approx(-4.0 * math.sin(pitch), abs=1e-4)
    assert points[1, 2] == pytest.approx(4.0 * math.sin(pitch), abs=1e-4)
