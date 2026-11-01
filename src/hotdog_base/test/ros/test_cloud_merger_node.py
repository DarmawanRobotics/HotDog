"""cloud_merger_node in process: two LiDAR clouds through TF become one cloud in base_link."""

from __future__ import annotations

import time

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')

from geometry_msgs.msg import TransformStamped  # noqa: E402
from hotdog_base.cloud_merger_node import CloudMergerNode  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from sensor_msgs.msg import PointCloud2  # noqa: E402
from std_msgs.msg import Header  # noqa: E402
from tf2_msgs.msg import TFMessage  # noqa: E402

from dharma_utils.ros import LATCHED, SENSOR, compat  # noqa: E402
from dharma_utils.ros.pointcloud import read_xyz, xyz_cloud  # noqa: E402
from dharma_utils.testing import Collector, Spinner, wait_for  # noqa: E402


def static_tf(child: str, x: float) -> TransformStamped:
    """Return base_link -> child at (x, 0, 0)."""
    t = TransformStamped()
    t.header.frame_id, t.child_frame_id = 'base_link', child
    t.transform.translation.x = x
    t.transform.rotation.w = 1.0
    return t


def cloud(frame: str, points) -> PointCloud2:
    """Return a cloud in a frame."""
    return xyz_cloud(Header(frame_id=frame), np.asarray(points, dtype=np.float32))


@pytest.fixture
def rig():
    compat.init()
    node = CloudMergerNode(
        parameter_overrides=[
            Parameter('level_source', value='none'),
            Parameter('robot.base_height', value=0.42),
        ]
    )
    helper = rclpy.create_node('cloud_merger_test_helper')
    merged = Collector(helper, PointCloud2, '/lidar/points', SENSOR)
    front = helper.create_publisher(PointCloud2, '/lidar/front/points', SENSOR)
    rear = helper.create_publisher(PointCloud2, '/lidar/rear/points', SENSOR)
    tf = helper.create_publisher(TFMessage, '/tf_static', LATCHED)
    tf.publish(
        TFMessage(transforms=[static_tf('front_lidar', 0.3), static_tf('rear_lidar', -0.3)])
    )
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(helper)
    spinner = Spinner(executor)
    assert wait_for(lambda: front.get_subscription_count() and rear.get_subscription_count(), 5.0)
    yield node, merged, front, rear
    spinner.stop()
    helper.destroy_node()
    node.destroy_node()
    compat.try_shutdown()


def test_clouds_merge_in_base_link(rig):
    _, merged, front, rear = rig

    def send():
        rear.publish(cloud('rear_lidar', [[2.0, 0.0, 0.0]]))  # yaw 180: behind the robot
        time.sleep(0.02)
        front.publish(cloud('front_lidar', [[2.0, 0.0, 0.0]]))

    assert wait_for(lambda: send() or merged.last is not None, 5.0, period=0.1)
    msg = merged.last
    assert msg.header.frame_id == 'base_link'
    xs = sorted(read_xyz(msg)[:, 0].tolist())
    assert xs == pytest.approx([-2.3, 2.3], abs=1e-4)


def test_missing_rear_cloud_publishes_nothing(rig):
    _, merged, front, _ = rig
    for _ in range(10):
        front.publish(cloud('front_lidar', [[2.0, 0.0, 0.0]]))
        time.sleep(0.05)
    assert merged.last is None
