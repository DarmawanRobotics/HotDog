# Localization

`dharma_localization` puts the robot on a site's map and keeps it there: a gravity-aligned
bridge from the LiDAR-inertial odometry into the robot's TF tree, and a fiducial-anchored
SE(2) EKF over `map -> odom`.

![TF tree](../diagrams/svg/tf_tree.svg)

## The bridge

FAST-LIO publishes `camera_init -> body`: its IMU at the start and now. Localization adds two
static transforms, `odom -> camera_init = L · T_base_imu` and `body -> base_link = T_base_imu⁻¹`
(`T_base_imu` from the URDF, `L` the roll and pitch of the base measured by the IMU while the
robot stands still at the odometry start). So `odom` starts at `base_link`, with z up and x the
start heading, even when the robot started on a slope. After `odometry/restarted` it levels
again.

## The estimator

![Localization EKF](../diagrams/svg/localization_ekf.svg)

- **State:** `map -> odom` (x, y, yaw) with a 3×3 covariance.
- **Predict:** noise per metre travelled and per radian turned by the odometry
  (`estimator.sigma_xy_per_sqrt_m`, ...), so a robot standing still never grows uncertain.
- **Update:** a measurement of `map -> base_link` from a tag in view (noise growing with distance
  and view angle) or from scan matching. The innovation is on the robot pose, so a fix far from
  the odometry origin is judged by how far it moves the robot.
- **Gate:** automatic corrections pass a chi-square test on the innovation
  (`estimator.gate_confidence`, 0.99): the gate opens as uncertainty grows after a long drive and
  is tight right after a correction.
- **Explicit:** `localization/start` (a tag in view), a 2D Pose Estimate (`/initialpose`) and
  `localization/assume_origin` set `map -> odom` directly, so a far but consistent tag still
  relocalizes after the robot was carried away.
- **Status:** `localization/status` is `NONE`, `LOCALIZED` or `UNCERTAIN` (sigma above
  `estimator.max_sigma_xy` or `max_sigma_yaw_deg`) with the source and the sigmas;
  `localization/pose` carries the pose with its covariance.

## Tags

A site's map frame is the frame its tags were recorded in: a tag in view puts the robot back on
that map wherever it starts. Any detector works that puts the tag frames under the camera optical
frame on TF: `apriltag_ros` with a throttled camera (the bringup's `fiducials:=true`), or
dharma_perception's `aruco_detector_node` for printed ArUco markers
(`fiducials_detector:=aruco`; `aruco_detector_node` `dictionary`, `ids`, `frames`, `sizes`).
Both publish the same tag convention (z toward the viewer, x to its left, y down), so a site's
tags file works with either.

```bash
ros2 service call /localization/load_tags dharma_interfaces/srv/LoadFile "{path: lobby/tags.json, create: true}"
ros2 service call /localization/start std_srvs/srv/Trigger          # localize from a tag in view
ros2 service call /localization/record_tags std_srvs/srv/Trigger    # add the visible tags (LOCALIZED only)
```

`record_tags` averages the visible tags' map poses over `tag.record_duration_sec`, refuses noisy
recordings and never records the tag the current `map -> odom` came from. The site manager loads
the active site's tags file for you ([Mapping and Sites](Mapping-and-Sites.md)).

## Scan matching

With `scan_match.enabled` the node matches `/cloud_registered_body` against `/map` (correlative
matcher on a likelihood field) and feeds the result through the same gate. It is off by default.

## Tuning hints

- Drift too fast or too slow for the corrections: `estimator.sigma_xy_per_sqrt_m` and the yaw
  noise per metre / per radian (measure the odometry drift on a loop).
- Tags far away or seen at a grazing angle are ignored (`tag.max_distance_m`, 4 m;
  `tag.max_view_angle_deg`, 60°).
- `UNCERTAIN` too often: the sigma limits, or more tags on the route.
