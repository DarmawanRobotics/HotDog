<div align="center">

# Dharma

**A robot-agnostic ROS 2 autonomy stack for legged and wheeled service robots: LiDAR-inertial
odometry, fiducial localization, occupancy mapping with sites, path finding and following, a
safety mux with a protective field, health monitoring and a simulator. This repository is the
hub of the stack and the template a robot product starts from.**

[![CI](https://github.com/DarmawanRobotics/Dharma/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DarmawanRobotics/Dharma/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-guide%20%C2%B7%20manual%20%C2%B7%20paper-4a6a9a)](docs/README.md)
[![ROS 2](https://img.shields.io/badge/ROS%202-Foxy%20%7C%20Humble%20%7C%20Jazzy-22314E?logo=ros&logoColor=white)](https://docs.ros.org/)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04%20%7C%2022.04%20%7C%2024.04-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/server)
![Python](https://img.shields.io/badge/Python-3.8%20%7C%203.10%20%7C%203.12-3776AB?logo=python&logoColor=white)
[![Docker](https://img.shields.io/badge/dev-Docker%20%2B%20VNC-2496ED?logo=docker&logoColor=white)](compose.yaml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

[Repositories](#repositories) · [Architecture](#architecture) · [Quick start](#quick-start) ·
[Bringup](#bringup) · [Scripts](#scripts) · [Guide](docs/guide/README.md) · [Manual (PDF)](docs/pdf/dharma_manual.pdf) · [Paper (PDF)](docs/pdf/dharma_paper.pdf)

</div>

---

Dharma knows nothing about a particular robot: geometry, limits and frames come from one robot
profile (`robot.*` parameters) that a product passes to every node, and the robot driver is a
separate package in the product. A product (a tour guide, an inspection robot, ...) is a
repository made from this template: its bringup package, its robot profile and its own features.

## Repositories

One repository per part, all at version 0.2.0, listed in [dharma.repos](dharma.repos):

| Repository                                                                     |                                                                                                                    |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| [dharma_utils](https://github.com/DarmawanRobotics/dharma_utils)               | math, typed configuration, the robot profile, the braking model, file IO, grids, `DharmaNode`, test helpers        |
| [dharma_interfaces](https://github.com/DarmawanRobotics/dharma_interfaces)     | typed status messages, sector scans, waypoints and the services of the stack                                       |
| [dharma_odometry](https://github.com/DarmawanRobotics/dharma_odometry)         | FAST-LIO / Leg-KILO (or an external estimator) behind a still-start gate, and the odometry monitor                 |
| [dharma_localization](https://github.com/DarmawanRobotics/dharma_localization) | gravity-aligned odometry bridge, fiducial-anchored SE(2) EKF over `map -> odom`, scan matching                     |
| [dharma_perception](https://github.com/DarmawanRobotics/dharma_perception)     | LiDAR to front (avoidance) and 360° (safety) sector scans, fail-safe when blind; AprilTag throttle, ArUco detector |
| [dharma_mapping](https://github.com/DarmawanRobotics/dharma_mapping)           | occupancy grids per site, crash-safe maps, sites (map, fiducials, routes), route recorder                          |
| [dharma_navigation](https://github.com/DarmawanRobotics/dharma_navigation)     | planner, route loader, path follower, obstacle avoidance, docking and charging; **dharma_control**: the safety mux |
| [dharma_health](https://github.com/DarmawanRobotics/dharma_health)             | sensor rates and stamp ages, TF ages, stack states and the computer as one `HealthStatus`                          |
| [dharma_rviz](https://github.com/DarmawanRobotics/dharma_rviz)                 | RViz panels and the robot layout                                                                                   |
| [dharma_sim](https://github.com/DarmawanRobotics/dharma_sim)                   | software-in-the-loop robot: kinematic body, ray-cast Mid-360, drifting odometry, scenarios                         |

[external.repos](external.repos) adds the Livox driver and FAST-LIO (and optionally Leg-KILO).

## Architecture

```
            ┌──────────────────────────────────────────────────────────────┐   ┌────────────────┐
 product    │ application: the product's features (tours, inspection, ...) │   │ safety         │
            ├──────────────────────────────────────────────────────────────┤   │                │
 navigation │ planner · route loader · path follower · obstacle avoidance  │   │ control mux:   │
            ├──────────────────────────────────────────────────────────────┤   │ the only       │
 world      │ occupancy grid · sites (map, fiducials, routes)              │   │ cmd_vel, e-stop│
            ├──────────────────────────────────────────────────────────────┤   │ protective     │
 estimation │ LiDAR-inertial odometry · localization (EKF) · sector scans  │   │ field          │
            ├──────────────────────────────────────────────────────────────┤   │ health monitor │
 robot      │ the robot driver (product package) or dharma_sim             │   │ speed scale    │
            └──────────────────────────────────────────────────────────────┘   └────────────────┘
 base         dharma_utils (robot profile, config, math, DharmaNode) · dharma_interfaces
```

- **Every node** subclasses `DharmaNode`: typed parameters validated on start and on every
  `ros2 param set`, the shared robot profile, structured logs, guarded timers.
- **Safety on the side**: navigation publishes `control/nav_cmd_vel`; the control mux arbitrates
  it against operator sources, applies the protective field on the 360° safety scan and the
  health speed scale, and is the only publisher of the driver's `cmd_vel`.
- **Frames** from `robot.frames` (`map -> odom -> base_link`); relative topic names; the product
  namespaces the driver (`/<ns>/cmd_vel`, `/<ns>/odom`).

## Quick start

**A new product**: on GitHub, _Use this template_, then

```bash
git clone https://github.com/<owner>/<MyRobot>.git && cd <MyRobot>
scripts/init_project.py --name MyRobot --package my_robot_bringup --robot-ns my_robot
pre-commit run --all-files          # re-pads the tables the rename made longer
git add -A && git commit -m "chore: init from the Dharma template"
```

**Dev container** (Linux / macOS, no local ROS needed):

```bash
scripts/dev.sh doctor              # Docker, memory, architecture, GitHub access (macOS: start here)
scripts/dev.sh up                  # imports the stack into src/, builds the image, starts it
scripts/dev.sh build               # colcon build (humble; --distro foxy|jazzy for the others)
scripts/dev.sh test
scripts/dev.sh shell               # then: ros2 launch robot_bringup sim.launch.py rviz:=true
scripts/dev.sh vnc                 # the desktop: vnc://localhost:5901 or noVNC on :6080
```

Foxy, Humble and Jazzy run side by side (`--distro foxy`: ports 5903 / 6082, `--distro jazzy`:
5902 / 6081), each with its own build, install and log volumes. VS Code: _Reopen in Container_
(`.devcontainer/`, `.devcontainer/foxy/`). **macOS** (Apple Silicon or Intel): Docker Desktop,
OrbStack or colima with at least 8 GB of memory; the images build natively for arm64, vcstool
is optional and `dev.sh` runs on the bash 3.2 of macOS; see
[Getting Started](docs/guide/Getting-Started.md#1-get-the-workspace).

**Natively** (Ubuntu 20.04 + Foxy, 22.04 + Humble or 24.04 + Jazzy, also the robot computer):

```bash
scripts/setup.sh check                        # what is there, what is missing
scripts/setup.sh install                      # tools, repos, livox, rosdep, build
scripts/setup.sh install timesync ptp         # robot computer: one clock (chrony, LiDAR PTP)
ros2 launch robot_bringup sim.launch.py       # the whole stack on the simulator
```

## Bringup

[src/robot_bringup](src/robot_bringup) is the placeholder product package
(`init_project.py` renames it):

| File                     |                                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `config/robot.yaml`      | the robot profile (`/**: ros__parameters: robot: ...`), validated at launch                                          |
| `config/stack.yaml`      | per-node overrides of the package defaults for this robot                                                            |
| `config/sim.yaml`        | what differs on the simulator                                                                                        |
| `launch/robot.launch.py` | odometry, localization, perception, mapping, navigation, control, health; driver with `robot_driver:=<pkg>[/<file>]` |
| `launch/sim.launch.py`   | the same stack on dharma_sim (odometry external)                                                                     |
| `robot_bringup/stack.py` | the composition: which package launch files, with which arguments                                                    |

Details in the [package README](src/robot_bringup/README.md).

## Scripts

| Script                    |                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `scripts/dev.sh`          | dev container: `up`, `shell`, `build`, `test`, `vnc`, `down`, `clean`, `import`, `doctor`; `--distro foxy\|humble\|jazzy` |
| `scripts/setup.sh`        | robot / dev machine: `check`, `install ros tools repos livox rosdep build service`                                        |
| `scripts/start_tmux.sh`   | tmux session with one window per subsystem (`robot` or `sim` layout in `scripts/tmux/`)                                   |
| `scripts/init_project.py` | turn the template into a product                                                                                          |
| `scripts/sync_tooling.sh` | maintainers: copy `tooling/` (lint configuration, per-repository CI) into every `dharma_*` checkout                       |

## Docs

- **[Guide](docs/guide/README.md)**: getting started, architecture, safety, every subsystem,
  operation and development (Markdown, renders on GitHub).
- **[Technical manual (PDF)](docs/pdf/dharma_manual.pdf)** and **[paper (PDF)](docs/pdf/dharma_paper.pdf)**;
  their LaTeX sources and the diagrams are in [docs/](docs/README.md) (`make -C docs pdf`).
  Conventions for code, commits and releases: [CONTRIBUTING.md](CONTRIBUTING.md); changes:
  [CHANGELOG.md](CHANGELOG.md).

Dharma is released under the [Apache License 2.0](LICENSE).
