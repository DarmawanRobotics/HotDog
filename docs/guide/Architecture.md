# Architecture

![Layers](../diagrams/svg/layers.svg)

Dharma is layered like a service robot's software usually is, with one difference: **safety is
not a layer on top but a column on the side**. Navigation never commands the robot; it proposes
`control/nav_cmd_vel`, and the control mux, the only publisher of the robot's `cmd_vel`, decides
what reaches the driver.

| Layer                  | Packages                                                              |
| ---------------------- | --------------------------------------------------------------------- |
| application            | the product's features (tours, inspection, ...), not part of Dharma   |
| navigation             | planner, route loader, path follower, reactive avoidance              |
| world model            | occupancy grid, sites (map, fiducials, routes)                        |
| estimation, perception | LiDAR-inertial odometry, localization (EKF), sector scans             |
| robot                  | the robot driver (a product package) or dharma_sim                    |
| safety (side)          | control mux: arbitration, envelope, protective field, e-stop; health  |
| base                   | dharma_utils (profile, config, math, `DharmaNode`), dharma_interfaces |

## Data flow

![Data flow](../diagrams/svg/dataflow.svg)

The main topics are listed in [Topics and Services](Topics-and-Services.md). Names are relative;
the product namespaces the driver (`/<ns>/cmd_vel`, `/<ns>/odom`, `/<ns>/battery`).

## Frames

![TF tree](../diagrams/svg/tf_tree.svg)

`map -> odom -> camera_init -> body -> base_link`. The estimator (FAST-LIO) publishes
`camera_init -> body` (its IMU at the start and now); localization bridges it into the robot's
tree with two static transforms and keeps `map -> odom`. `odom` is **gravity-aligned**: the
bridge levels it with the IMU while the robot stands still at the start, so a robot that started
on a slope does not tilt its map. Frame names come from `robot.frames`; nothing is hard-coded.
Details: [Localization](Localization.md).

## One robot profile

Every node reads the same `robot.*` parameters: kinematics, footprint, base height, limits and
frames. The planner's radii, the protective field, the braking model, the self filter of
perception and the jump limits of odometry and mapping all derive from it. See
[Robot Profile](Robot-Profile.md).

## Inside a package

```
<pkg>/
  <pkg>/<name>_node.py   thin ROS nodes (DharmaNode): parameters, topics, services, timers
  <pkg>/core/            pure Python + numpy: algorithms, state machines, config dataclasses
  <pkg>/utils/           message <-> core conversions, markers
  config/<pkg>.yaml  launch/<pkg>.launch.py  test/unit  test/ros  test/test_style.py
```

- `core/` never imports ROS, so every algorithm is unit-tested without it.
- Parameters are typed dataclasses: ranges, units and descriptions are declared once, validated
  at start and on every `ros2 param set`; safety values are read-only at runtime.
- Algorithm families are plugins (`dharma.controllers`, `dharma.avoidance`,
  `dharma_health.checks`): a product adds one without forking.
- Status messages are typed and latched (`OdometryStatus`, `LocalizationStatus`,
  `NavigationStatus`, `ControlStatus`, `HealthStatus`, ...), never JSON strings.

## Repositories

![Repositories](../diagrams/svg/repos.svg)

`dharma_utils` and `dharma_interfaces` are at the bottom; every package depends on them and on
nothing above its layer. Each repository has the same CI (lint, then build and test on Foxy,
Humble and Jazzy, with the Dharma dependencies on the same branch when it exists):

![CI](../diagrams/svg/ci.svg)
