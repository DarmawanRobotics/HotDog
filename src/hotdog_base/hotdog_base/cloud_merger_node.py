"""
cloud_merger_node: the front and rear RoboSense Airy of the M20 as one PointCloud2 in base_link.

Each input is moved into the base frame through TF (the URDF's front_lidar_link and
rear_lidar_link) when it arrives; the merged, self-filtered cloud is published when the first
input arrives and every other input is fresh. With level_source imu the body's roll and pitch
(from the robot's IMU) are removed, so lidar_sector_node runs with level_source none.
"""

from __future__ import annotations

import time

from sensor_msgs.msg import Imu, PointCloud2
from std_msgs.msg import Header

from dharma_utils.ros import SENSOR, DharmaNode, run
from dharma_utils.ros.pointcloud import CloudError, read_xyz, xyz_cloud
from dharma_utils.ros.time import to_sec, to_stamp
from hotdog_base.core.config import MergerConfig
from hotdog_base.core.merge import CloudMerger, level_rotation


class CloudMergerNode(DharmaNode):
    """Merges the robot's LiDAR clouds into one cloud for perception and health."""

    def __init__(self, **kwargs):
        super().__init__('cloud_merger_node', **kwargs)
        self.config = self.declare_config(MergerConfig).value
        self.robot = self.declare_robot().value
        self.base = self.robot.frames.base
        self.merger = CloudMerger(self.config, self.robot)
        self.attitude = None  # (orientation quaternion, monotonic receive time)
        self.cloud_pub = self.create_publisher(PointCloud2, self.config.output_topic, SENSOR)
        for index, topic in enumerate(self.config.inputs):
            self.create_subscription(
                PointCloud2, topic, lambda msg, i=index: self.on_cloud(i, msg), SENSOR
            )
        if self.config.level_source == 'imu':
            self.create_subscription(Imu, self.config.imu_topic, self.on_imu, SENSOR)
        self.log.info(
            'cloud merger',
            inputs=','.join(self.config.inputs),
            output=self.config.output_topic,
            base=self.base,
            level=self.config.level_source,
        )

    def on_imu(self, msg: Imu):
        """Keep the body attitude (only once the driver knows its angle unit)."""
        if msg.orientation_covariance[0] < 0.0:
            return
        q = msg.orientation
        self.attitude = ((q.x, q.y, q.z, q.w), time.monotonic())

    def on_cloud(self, index: int, msg: PointCloud2):
        """Move one input into the base frame; merge and publish on the trigger input."""
        frame = msg.header.frame_id
        sensor_to_base = self.tf.static(self.base, frame)
        if sensor_to_base is None:
            self.log.warning('no TF for a LiDAR', frame=frame, base=self.base, throttle=5.0)
            return
        try:
            points = read_xyz(msg)
        except CloudError as error:
            self.log.warning('unusable cloud', input=self.config.inputs[index],
                             error=str(error), throttle=5.0)  # fmt: skip
            return
        now = time.monotonic()
        self.merger.update(index, self.merger.to_base(index, points, sensor_to_base),
                           to_sec(msg.header.stamp), now)  # fmt: skip
        if index == 0:
            self.publish(now)

    def level(self, now: float):
        """Return the leveling rotation, None while the attitude is unknown or stale."""
        if self.config.level_source != 'imu' or self.attitude is None:
            return None
        quat, received = self.attitude
        if now - received > self.config.imu_max_age_sec:
            self.log.warning('IMU attitude stale: cloud not leveled', throttle=10.0)
            return None
        rotation = level_rotation(quat, self.config.max_level_deg)
        if rotation is None:
            self.log.warning('body tilt implausible: cloud not leveled', throttle=10.0)
        return rotation

    def publish(self, now: float):
        """Publish the merged cloud, or say which input is missing."""
        merged = self.merger.merge(now, self.level(now))
        if merged is None:
            stale = [self.config.inputs[i] for i in self.merger.stale(now)]
            self.log.warning('LiDAR input stale: no merged cloud', stale=','.join(stale),
                             throttle=5.0)  # fmt: skip
            return
        points, stamp = merged
        header = Header(frame_id=self.base, stamp=to_stamp(stamp))
        self.cloud_pub.publish(xyz_cloud(header, points))


def main(args=None):
    """Run cloud_merger_node."""
    run(CloudMergerNode, args=args)


if __name__ == '__main__':
    main()
