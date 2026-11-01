# robot_bringup

The bringup of a robot on the Dharma stack: its robot profile, the per-node overrides of the
package defaults, and one launch for the whole stack (plus the same stack on the simulator).

## Files

| File                            |                                                                                                 |
| ------------------------------- | ----------------------------------------------------------------------------------------------- |
| `config/robot.yaml`             | the robot profile, `/**: ros__parameters: robot: {...}` (kinematics, footprint, limits, frames) |
| `config/stack.yaml`             | per-node overrides for this robot (only what differs from the package defaults)                 |
| `config/sim.yaml`               | on top of `stack.yaml` in `sim.launch.py` (PointCloud2 input, the simulator's topics)           |
| `launch/robot.launch.py`        | the robot driver (optional) and the stack                                                       |
| `launch/sim.launch.py`          | dharma_sim and the stack (odometry external, no camera)                                         |
| `robot_bringup/stack.py`        | the composition: package launch files, their arguments, the nodes they start                    |
| `robot_bringup/bringup.py`      | argument validation, the robot profile check, parameter file merging                            |
| `robot_bringup/launch_utils.py` | the launch actions shared by both launch files                                                  |

## Launch

```bash
ros2 launch robot_bringup robot.launch.py                                   # the stack
ros2 launch robot_bringup robot.launch.py robot_driver:=my_driver site:=lobby
ros2 launch robot_bringup robot.launch.py site:=lobby start_mapping:=true   # map a new site
ros2 launch robot_bringup sim.launch.py rviz:=true scenario:=person_crossing
```

| Argument                       | Default (env)           |                                                                                                                                   |
| ------------------------------ | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `robot_params`                 | `config/robot.yaml`     | robot profile file                                                                                                                |
| `params_file`                  |                         | parameters on top of `config/stack.yaml`                                                                                          |
| `use_sim_time` / `log_level`   | / `info`                |                                                                                                                                   |
| `robot_ns`                     | `robot` (`ROBOT_NS`)    | driver namespace: `/<ns>/cmd_vel`, `/<ns>/odom`, `/<ns>/battery`                                                                  |
| `robot_driver`                 | (`ROBOT_DRIVER`)        | `<package>[/<file>.launch.py]` (default file `bringup.launch.py`), started with `namespace:=<robot_ns>`; empty: started elsewhere |
| `odometry`                     | `fast_lio` (`ODOMETRY`) | `fast_lio`, `leg_kilo` or `external` (robot launch only)                                                                          |
| `site` / `sites_dir`           | (`SITE`, `SITES_DIR`)   | empty: from the parameter files (or the last site)                                                                                |
| `start_mapping`                | `false`                 | map `site` from the start when it is new (odometry keeps its map)                                                                 |
| `fiducials`                    | `true` (sim `false`)    | camera throttle + tag detector                                                                                                    |
| `fiducials_detector`           | `apriltag`              | `apriltag` (apriltag_ros) or `aruco` (dharma_perception `aruco_detector_node`), both publish the tags on TF                       |
| `camera_image` / `camera_info` |                         | empty: the perception defaults                                                                                                    |
| `health`                       | `true`                  | start the health monitor                                                                                                          |
| `world` / `scenario` / `rviz`  | / / `false`             | simulator only                                                                                                                    |

What the launch does:

1. Validates every argument and the robot profile (`dharma_utils.robot.RobotProfile`: unknown
   names and out-of-range values stop the launch with the reason).
2. Merges `config/stack.yaml` (+ `config/sim.yaml`) and `params_file` into one parameter file
   (later wins, parameter by parameter), adds every started node to the health monitor's
   `nodes.expected` (names already listed there, e.g. the driver's, are kept), and reports
   sections that match no node (typos) and `/**` parameters besides `robot.*`: Foxy applies a
   node's own section after `/**` whatever the file order, so put overrides under the node name.
3. Includes each package launch (`dharma_odometry`, `dharma_localization`, `dharma_perception`,
   `dharma_mapping`, `dharma_navigation`, `dharma_control`, `dharma_health`) with
   `robot_params`, the merged `params_file` and only the arguments that are set. Each include runs
   in its own launch scope: no argument of this launch leaks into a package launch (Foxy has no
   `GroupAction(forwarding=False)`: the scope unsets this launch's arguments instead).
4. Remaps the control mux's `cmd_vel` to `/<robot_ns>/cmd_vel` (the only publisher); navigation
   reads `/<robot_ns>/battery` and `/<robot_ns>/odom`, the odometry monitor `/<robot_ns>/odom`.

A robot driver package provides `launch/bringup.launch.py` (or the file named) accepting
`namespace`; it publishes `/<ns>/odom`, `/<ns>/battery`, the LiDAR and IMU, the URDF TF, and
subscribes `/<ns>/cmd_vel`.

## Tests

`test/unit` (argument validation, parameter merging, the composition), `test/ros` (both launch
files against stub packages, and `ros2 launch --show-args` when installed), `test/test_style.py`.

```bash
colcon build --packages-select robot_bringup && colcon test --packages-select robot_bringup
```
