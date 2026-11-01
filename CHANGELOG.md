# Changelog

All notable changes to HotDog. Format: [Keep a Changelog](https://keepachangelog.com), versions follow [SemVer](https://semver.org).

## [Unreleased]

### Added

- `hotdog` from the Dharma template, on ROS 2 Foxy only.
- The Lynx M20 as the robot: `m20_bringup` started by `robot.launch.py`, its own odometry as
  the odometry (`camera_init -> body`), no mapping, the odometry start as the map origin.
- `hotdog_base`: both RoboSense Airy through `rslidar_sdk`, merged, self-filtered and leveled
  into `/lidar/points` for perception (360° sectors) and health.
- `hotdog_inspection` and `hotdog_interfaces`: inspection at every stop point (the follower's
  hook), points matched by position from `<site>/inspection.yaml`, overheat analysis with the
  UniPod MT11 (absolute, over ambient, between similar components), reports with thermal and
  visible images, `inspection/add_target` to teach targets from the pod's view.
- The bringup starts `unipod_driver` (`pod`, `pod_ip`) and `inspection_node` (`inspection`);
  `sites_dir` defaults to `~/.hotdog/sites` for every node.
