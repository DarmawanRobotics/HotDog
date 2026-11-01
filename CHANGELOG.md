# Changelog

All notable changes to HotDog. Format: [Keep a Changelog](https://keepachangelog.com), versions follow [SemVer](https://semver.org).

## [Unreleased]

### Added

- `hotdog` from the Dharma template, on ROS 2 Foxy only.
- The Lynx M20 as the robot: `m20_bringup` started by `robot.launch.py`, its own odometry as
  the odometry (`camera_init -> body`), no mapping, the odometry start as the map origin.
- `hotdog_base`: both RoboSense Airy through `rslidar_sdk`, merged, self-filtered and leveled
  into `/lidar/points` for perception (360° sectors) and health.
