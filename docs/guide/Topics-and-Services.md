# Topics and Services

All names are relative (the stack can run in a namespace); the robot driver's topics are
namespaced by the product (`/<ns>/cmd_vel`, `/<ns>/odom`, `/<ns>/battery`). Status topics are
latched and typed (enum constants in `dharma_interfaces`). Each package README has the complete
list; the manual's interfaces chapter lists every field of every message and service.

## Per package

| Package      | Publishes                                                                                                                                                                                   | Subscribes                                                                                                                                       | Services                                                                                                                                                   |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| odometry     | `odometry/status`, `odometry/restarted` (Empty)                                                                                                                                             | `/Odometry`, leg odometry (optional), IMU                                                                                                        | —                                                                                                                                                          |
| localization | TF `map -> odom` and the bridge, `localization/status`, `localization/pose`, `localization/tag_markers`                                                                                     | `odometry/restarted`, `/initialpose`, `/livox/imu`, `/map` and `/cloud_registered_body` (scan matching)                                          | `localization/start`, `reset`, `assume_origin`, `record_tags`, `load_tags`                                                                                 |
| perception   | `perception/sector_scan` (front), `perception/safety_scan` (360°), `perception/obstacles`                                                                                                   | `livox/lidar` (CustomMsg) or a PointCloud2, TF                                                                                                   | —                                                                                                                                                          |
| mapping      | `/map`, `mapping/grid`, `mapping/status`, `site/status`, `route/saved`                                                                                                                      | `/cloud_registered_body`, `localization/status`                                                                                                  | `site/list`, `site/load`, `mapping/start`, `mapping/stop`, `mapping/save`, `route/start`, `route/stop`, `route/mark_stop_point`                            |
| navigation   | `planner/path`, `planner/status`, `planner/costmap`, `navigation/status`, `navigation/stop_point`, `navigation/path`, `navigation/waypoints`, `navigation/avoidance`, `control/nav_cmd_vel` | `/map`, `perception/*_scan`, `control/status`, `localization/status`, `battery`, `odom`                                                          | `planner/go_to`, `planner/plan`, `planner/cancel`, `navigation/set_path`, `navigation/load_path`, `navigation/start`, `navigation/stop`, `pause`, `resume` |
| control      | `cmd_vel` (the only publisher), `control/status`                                                                                                                                            | `control/nav_cmd_vel`, `control/remote/<source>/cmd_vel`, `perception/safety_scan`, `control/estop_request`, `control/hw_estop`, `health/status` | `control/set_mode`, `control/estop/engage`, `control/estop/release`                                                                                        |
| health       | `health/status`, `diagnostics`                                                                                                                                                              | the configured sensor topics, the status topics, `perception/safety_scan`, TF                                                                    | —                                                                                                                                                          |
| sim          | `/<ns>/odom`, `/<ns>/battery`, `/Odometry`, `/cloud_registered_body`, `/livox/imu`, TF, `sim/ground_truth`, `sim/collision`, `/initialpose`                                                 | `/<ns>/cmd_vel`, `sim/obstacles`, `localization/status`                                                                                          | `sim/inspect`                                                                                                                                              |

## Messages and services (dharma_interfaces 0.2.0)

| Kind     | Names                                                                                                                                                                                                                                                                       |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| status   | `OdometryStatus`, `LocalizationStatus`, `MappingStatus`, `SiteStatus`, `PlannerStatus`, `NavigationStatus`, `ControlStatus`, `HealthStatus`                                                                                                                                 |
| data     | `SectorScan` (`ranges <= BLOCKED` (0) or NaN: blocked or unknown, an obstacle at the robot), `AvoidanceCommand` (heading_offset rad, yaw_rate_bias rad/s, lateral_bias, velocity_scale, emergency), `Waypoint` (x, y, yaw rad, dwell_sec), `WaypointPath`, `StopPointEvent` |
| services | `GoTo` (x, y, yaw), `PlanPath`, `SetPath`, `LoadPath`, `LoadFile` (path inside the sites dir), `ListSites`, `LoadSite`, `StartMapping`, `MarkStopPoint`, `SetMode` (`auto` / `remote` + source)                                                                             |

Safety actions are separate `std_srvs/Trigger` services (`control/estop/engage`,
`control/estop/release`), never a `SetBool` whose default request could release something.

## Everyday commands

```bash
ros2 service call /planner/go_to dharma_interfaces/srv/GoTo "{x: 8.0, y: 4.0, yaw: 1.57}"
ros2 service call /planner/cancel std_srvs/srv/Trigger
ros2 service call /navigation/load_path dharma_interfaces/srv/LoadPath "{path: lobby/routes/patrol.csv}"
ros2 service call /navigation/start std_srvs/srv/Trigger
ros2 service call /navigation/pause std_srvs/srv/Trigger
ros2 service call /navigation/resume std_srvs/srv/Trigger
ros2 service call /control/set_mode dharma_interfaces/srv/SetMode "{mode: remote, source: handheld}"
ros2 service call /control/estop/engage std_srvs/srv/Trigger
ros2 service call /control/estop/release std_srvs/srv/Trigger
ros2 topic echo /navigation/status
ros2 topic echo /health/status
```
