# Getting Started

Run the whole stack on the simulator in a few minutes, then on a robot.

## 1. Get the workspace

The [Dharma hub](https://github.com/DarmawanRobotics/Dharma) is the workspace: `dharma.repos`
lists every stack repository, `external.repos` the Livox driver and FAST-LIO.

**Dev container** (Linux or macOS, no local ROS needed):

```bash
git clone https://github.com/DarmawanRobotics/Dharma.git && cd Dharma
scripts/dev.sh up        # imports the stack into src/, builds the image, starts the container
scripts/dev.sh build     # colcon build (Humble; --distro foxy or --distro jazzy)
scripts/dev.sh test      # colcon test + test-result
scripts/dev.sh shell     # a shell with ROS and the workspace sourced
scripts/dev.sh vnc       # desktop: vnc://localhost:5901 or http://localhost:6080/vnc.html
```

Foxy, Humble and Jazzy run side by side (`--distro foxy`: ports 5903 / 6082, `--distro jazzy`:
5902 / 6081) with separate build, install and log volumes. VS Code: _Reopen in Container_.

**On a Mac** (Apple Silicon or Intel), the same commands:

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or OrbStack, or
   colima with `--vm-type vz --mount-type virtiofs`) and give it **at least 8 GB of memory**
   and 4+ CPUs (_Settings > Resources_): FAST-LIO and PCL need it to compile.
2. Give git access to the private repositories: `gh auth login` (or an SSH key on GitHub).
3. `scripts/dev.sh doctor` checks Docker, compose, memory, the architecture and GitHub access.
4. `scripts/dev.sh up`, `build`, `test`, `shell` as above. The images build natively for
   arm64 (the ROS images are multi-arch): no Rosetta / qemu emulation. vcstool is optional,
   `dev.sh` imports with plain git without it, and it runs on the bash 3.2 of macOS.
5. The desktop: `scripts/dev.sh vnc` opens Screen Sharing (password `dharma`), or use
   noVNC in a browser at http://localhost:6080/vnc.html. RViz renders in software.

The workspace is bind-mounted (edit with any Mac editor); `build/`, `install/` and `log/` live
in Docker volumes, so colcon never builds on the slower shared file system. Low on memory:
`scripts/dev.sh build --parallel-workers 1`.

**Natively** (Ubuntu 20.04 + Foxy, 22.04 + Humble or 24.04 + Jazzy, also on the robot computer):

```bash
scripts/setup.sh check      # what is installed, what is missing
scripts/setup.sh install    # tools, repos, Livox SDK, rosdep, build
source install/setup.bash
```

On the robot computer, also put every stamp on one clock (chrony, PTP for the LiDAR; see
[Time synchronisation](Troubleshooting.md#time-synchronisation)):

```bash
TIME_SERVERS=<server> TIME_ALLOW=<subnet> LIDAR_IP=<ip> scripts/setup.sh install timesync ptp
```

## 2. Run on the simulator

```bash
ros2 launch robot_bringup sim.launch.py rviz:=true
```

This starts [dharma_sim](Simulation.md) (a kinematic robot with a simulated Mid-360 and drifting
odometry in a small mall) and the whole stack with odometry `external`. The simulator publishes
`/initialpose` while the robot is not localized, so localization starts by itself.

In RViz, the **Mission** panel drives the robot:

1. use _2D Goal Pose_ to fill in a goal, then **Go** (`planner/go_to`);
2. watch `navigation/status` and the planned path; press **E-STOP** on the **Safety** panel at
   any time, **Release**, then **Resume** on the Mission panel.

The same from a terminal:

```bash
ros2 service call /planner/go_to dharma_interfaces/srv/GoTo "{x: 4.5, y: 3.0, yaw: 3.14}"
ros2 topic echo /navigation/status
ros2 service call /control/estop/engage std_srvs/srv/Trigger
```

Dock and charge: the robot drives to the dock (its tag `charging_dock` is on the west wall of
the mall), centres on the tag, walks in, sits down and charges, then undocks
([Navigation](Navigation.md#docking-and-charging)):

```bash
ros2 service call /planner/go_to dharma_interfaces/srv/GoTo "{x: -4.3, y: 0.0, yaw: 3.14}"
ros2 service call /docking/dock std_srvs/srv/Trigger
ros2 topic echo /docking/status            # ... APPROACHING, SITTING, CHARGING, DOCKED
ros2 service call /docking/undock std_srvs/srv/Trigger
```

Add people with a scenario (`scenario:=person_crossing`) or by hand:

```bash
ros2 topic pub --once /sim/obstacles geometry_msgs/msg/PoseArray "{poses: [{position: {x: 2.0, y: -3.0}}]}"
```

## 3. On a robot

1. Make a product from the template and fill in the robot profile:
   [New Product from Template](New-Product-from-Template.md), [Robot Profile](Robot-Profile.md).
2. Measure the braking limits ([Robot Profile](Robot-Profile.md#measure-the-braking-limits)).
3. Map the site, record its tags, teach routes: [Mapping and Sites](Mapping-and-Sites.md).
4. `ros2 launch robot_bringup robot.launch.py site:=<site>`.

Keep a hardware e-stop at hand: Dharma's safety layer is a software channel, see
[Safety](Safety.md).
