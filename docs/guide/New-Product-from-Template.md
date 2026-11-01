# New Product from Template

A robot product (a tour guide, an inspection robot, ...) is its own repository made from the
[Dharma hub](https://github.com/DarmawanRobotics/Dharma), which is a GitHub template. The product
holds its bringup package, its robot profile, its driver integration and its own features;
Dharma stays unchanged underneath.

## 1. Create the repository

On GitHub: **Use this template**, then:

```bash
git clone https://github.com/<owner>/<MyRobot>.git && cd <MyRobot>
scripts/init_project.py --name MyRobot --package my_robot_bringup --robot-ns my_robot --dry-run
scripts/init_project.py --name MyRobot --package my_robot_bringup --robot-ns my_robot
pre-commit run --all-files          # re-pads the tables the rename made longer
git add -A && git commit -m "chore: init from the Dharma template"
```

`init_project.py` renames the `robot_bringup` placeholder everywhere, sets the robot namespace and
the container names, removes what only the hub needs (`tooling/`, the tooling sync, the script
itself; the manual, paper, diagrams, PDFs and guide unless `--keep-docs`), resets the version to 0.1.0
and rewrites `README.md` and `CHANGELOG.md`.

## 2. Describe the robot

Edit `config/robot.yaml` of the bringup package: kinematics, footprint, base height, limits and
frames ([Robot Profile](Robot-Profile.md)). The launch validates it and stops with the reason on an
unknown name or an out-of-range value.

## 3. Connect the driver

The robot driver is a separate package. It provides `launch/bringup.launch.py` (or another file)
accepting `namespace`; it publishes `/<ns>/odom`, `/<ns>/battery`, the LiDAR and IMU and the URDF
TF, and subscribes `/<ns>/cmd_vel`. It must stop on its own command timeout. Wire the hardware
e-stop to `control/hw_estop` ([Safety](Safety.md)).

```bash
ros2 launch my_robot_bringup robot.launch.py robot_driver:=my_driver           # or ROBOT_DRIVER=...
ros2 launch my_robot_bringup robot.launch.py odometry:=leg_kilo                 # fast_lio | leg_kilo | external
```

## 4. Per-node values

`config/stack.yaml` holds only what differs from the package defaults for this robot (e.g. the
camera topics, the health topics and nodes, the field margins). `config/sim.yaml` adds what
differs on the simulator. Check everything on the simulator first:

```bash
ros2 launch my_robot_bringup sim.launch.py rviz:=true
```

## 5. On the robot

1. One clock for every stamp: chrony for the computers and PTP for the LiDAR
   ([Troubleshooting](Troubleshooting.md#time-synchronisation)):
   `TIME_SERVERS=<server> TIME_ALLOW=<subnet> LIDAR_IP=<ip> scripts/setup.sh install timesync ptp`.
2. Measure the braking limits ([Robot Profile](Robot-Profile.md#measure-the-braking-limits)).
3. Map the first site, record its tags, teach a route ([Mapping and Sites](Mapping-and-Sites.md)).
4. `ros2 launch my_robot_bringup robot.launch.py site:=<site>`; for boot,
   `scripts/setup.sh install service` installs a systemd unit running the bringup.
5. Pin the Dharma release tags in `dharma.repos` once the robot works.

## 6. Add features

Product features live in the product: new nodes that use the Dharma interfaces (e.g. call
`planner/go_to`, listen to `navigation/stop_point` and answer the follower's inspection hook).
Algorithms that fit a Dharma family are plugins: a controller, an avoidance policy or a health
check registered through an entry point, without forking (example in the manual's development
chapter).
