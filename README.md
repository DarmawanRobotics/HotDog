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

`hotdog` brings the robot up: its profile (`config/robot.yaml`), the per-node overrides of the
stack (`config/stack.yaml`) and one launch for everything. The Dharma packages come from
[dharma.repos](dharma.repos).

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
