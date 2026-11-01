<div align="center">

# HotDog

**Autonomous substation patrol robot on the Deep Robotics Lynx M20: teach and repeat on the
robot's own odometry, thermal overheat analysis with the UniPod MT11 and partial discharge
detection with the Hertzinno HZ-FA-371 at every stop point. Built on the Dharma stack.**

[![CI](https://github.com/DarmawanRobotics/HotDog/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DarmawanRobotics/HotDog/actions/workflows/ci.yml)
[![ROS 2](https://img.shields.io/badge/ROS%202-Foxy-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/foxy/)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04-E95420?logo=ubuntu&logoColor=white)](https://releases.ubuntu.com/20.04/)
[![Dharma](https://img.shields.io/badge/stack-Dharma-4A78C2)](dharma.repos)
[![Docker](https://img.shields.io/badge/dev-Docker%20%2B%20VNC-2496ED?logo=docker&logoColor=white)](compose.yaml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

</div>

---

Substation (gardu induk) equipment is inspected on fixed rounds: the same disconnectors,
busbar joints, bushings and cable terminations, every shift. HotDog walks such a round on its
own, stops in front of each piece of equipment, points the pod at it and checks it for
overheating and partial discharge.

HotDog runs on **Dharma**, the shared autonomy stack, pinned in [dharma.repos](dharma.repos),
with the M20's own odometry instead of a LiDAR-inertial estimator and without maps: routes are
taught and repeated from the dock. The robot, its LiDARs and their drivers come from
[external.repos](external.repos).

## Packages

| Package                                                                                                                                                                                                                        | Role                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| [`hotdog`](src/hotdog)                                                                                                                                                                                                         | the robot: profile, M20 driver settings, stack config, `robot.launch.py`, `sim.launch.py`               |
| [`hotdog_base`](src/hotdog_base)                                                                                                                                                                                               | both RoboSense Airy as one leveled cloud in `base_link`, the shared launch helpers                      |
| [`hotdog_inspection`](src/hotdog_inspection)                                                                                                                                                                                   | inspection at the stop points: overheat (UniPod MT11), partial discharge (HZ-FA-371), reports, teaching |
| [`hotdog_patrol`](src/hotdog_patrol)                                                                                                                                                                                           | patrols from the dock, on demand or on a schedule, patrol summaries, back to the dock                   |
| [`hotdog_interfaces`](src/hotdog_interfaces)                                                                                                                                                                                   | findings, inspection reports and status, `AddTarget`                                                    |
| `dharma_*` ([dharma.repos](dharma.repos))                                                                                                                                                                                      | odometry monitor, localization, perception, routes, navigation, control mux, health                     |
| [m20_ros2](https://github.com/DarmawanRobotics/m20_ros2), [unipod_driver](https://github.com/DarmawanRobotics/unipod_driver), [rslidar_sdk](https://github.com/RoboSense-LiDAR/rslidar_sdk) ([external.repos](external.repos)) | M20 driver and URDF, the pod driver, the Airy driver                                                    |

<details>
<summary><b>Hardware</b></summary>

| Component  | Model                                           | Role                                                 |
| ---------- | ----------------------------------------------- | ---------------------------------------------------- |
| Robot base | Deep Robotics **Lynx M20** (wheel-legged)       | odometry, IMU, battery, motion (UDP protocol V1.3.0) |
| LiDAR      | 2 × RoboSense **Airy** (front, rear), 96 beams  | obstacle sectors, the 360° protective field          |
| Pod        | Reebot **UniPod MT11** (zoom + thermal, gimbal) | overheat analysis, evidence images                   |
| Acoustic   | Hertzinno **HZ-FA-371** acoustic camera         | partial discharge (corona, surface, floating)        |
| Compute    | payload computer, Ubuntu 20.04 + ROS 2 Foxy     | the whole stack                                      |

</details>

## Quick start

```bash
scripts/dev.sh up                     # dev container, ROS 2 Foxy
scripts/dev.sh build && scripts/dev.sh test
scripts/dev.sh shell
ros2 launch hotdog sim.launch.py rviz:=true                   # no robot needed
```

On the robot: `scripts/setup.sh install`, then `scripts/setup.sh install service`. The robot
driver runs in the namespace `/m20` (`/m20/cmd_vel`, `/m20/odom`).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the conventions.
