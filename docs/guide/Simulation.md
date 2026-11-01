# Simulation

`dharma_sim` is a software-in-the-loop robot: one node, `sim_robot_node`, stands in for the
robot driver, the Livox Mid-360 with its IMU and FAST-LIO. It is kinematic (no Gazebo, no GPU),
so the whole stack runs on a laptop and in CI.

```bash
ros2 launch robot_bringup sim.launch.py rviz:=true                       # the stack on the simulator
ros2 launch robot_bringup sim.launch.py scenario:=person_crossing rviz:=true
ros2 launch dharma_sim sim.launch.py robot_params:=robot.yaml site:=mall_loop   # the simulator alone
```

## What it models

| Model    |                                                                                                                      |
| -------- | -------------------------------------------------------------------------------------------------------------------- |
| body     | omni or diff from `robot.kinematics`, the profile's accelerations, measured time steps, stops and latches on contact |
| world    | walls and circles (pillars, people, boxes) with heights; correct ray casting also from inside a circle               |
| LiDAR    | Mid-360: vertical field of view −7°..52° from the mount height, 0.1–40 m, floor returns, range noise, point dropout  |
| odometry | drift per distance travelled (random walk), scale error, yaw bias; restarts                                          |
| latency  | sensor stamps `t − L` showing the state of that time; commands act `L` after they arrive                             |
| IMU      | specific force and yaw rate, at the Livox manual's IMU offset                                                        |

The body is planar: no gait, pitch or roll, no negative obstacles.

| On the robot       | In the simulator                                                              |
| ------------------ | ----------------------------------------------------------------------------- |
| driver             | `/<ns>/cmd_vel` in; `/<ns>/odom`, `/<ns>/battery` out                         |
| Mid-360 + FAST-LIO | `/cloud_registered_body`, `/Odometry`, TF `camera_init -> body`, `/livox/imu` |
| URDF               | static TF `base_link -> livox_frame -> livox_imu_frame`                       |
| a tag in view      | `/initialpose` at the true pose while `localization/status` is `NONE`         |
| inspection         | `sim/inspect` answers `clear`                                                 |
| people and boxes   | `sim/obstacles` (PoseArray, map frame) replaces the dynamic circles           |
| the truth          | `sim/ground_truth`, `sim/collision` (latched, true on contact)                |

There is no `/livox/lidar`: the bringup's `config/sim.yaml` switches perception to PointCloud2
input and health to `/cloud_registered_body`.

## Scenarios

Seeded YAML files in `config/scenarios/`: the same file gives the same run.

```yaml
seed: 3
latency: { lidar_sec: 0.15, odometry_sec: 0.05, command_sec: 0.05 }
odometry: { sigma_x: 0.01, scale_error: 0.01, yaw_bias_deg_per_m: 0.1 }
obstacles: # circles from start to end (default: forever), moving with vx, vy
  - { start: 8.0, end: 30.0, x: -1.5, y: -4.2, vy: 0.15, radius: 0.25, height: 1.7 }
dropouts: # lidar | odometry | imu | all
  - { start: 10.0, duration: 1.5, sensor: lidar }
odometry_restarts: [40.0]
```

| Scenario          |                                                                     |
| ----------------- | ------------------------------------------------------------------- |
| `drift`           | 1 % scale error, yaw bias and noise: localization corrections       |
| `person_crossing` | a person crosses the corridor, a box stays on the route             |
| `sensor_faults`   | LiDAR, odometry and full dropouts, an odometry restart, late stamps |

## Sites

`site:=mall_loop` draws a loadable site from the world into `sites_dir` (default
`/tmp/dharma_sim/sites`): `map.pgm` / `map.yaml`, `tags.json` and the taught loop
`routes/mall_loop.csv` with one stop point. Try a route:

```bash
ros2 service call /navigation/load_path dharma_interfaces/srv/LoadPath "{path: mall_loop/routes/mall_loop.csv}"
ros2 service call /navigation/start std_srvs/srv/Trigger
```

## In tests

The models are pure Python (`dharma_sim.core`): tests and experiments can drive the body, LiDAR,
drift and latency models directly with a seed, without ROS. The paper's experiments are built
this way (`experiments/` in the hub).
