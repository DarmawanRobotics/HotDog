# hotdog

The bringup of HotDog on the Lynx M20: the robot profile, the M20 driver settings, the
per-node overrides of the Dharma stack, and one launch for the whole robot (plus the same stack
on the simulator).

## Files

| File                     |                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| `config/robot.yaml`      | the robot profile, `/**: ros__parameters: robot: {...}` (kinematics, footprint, limits, frames) |
| `config/m20_driver.yaml` | m20_driver as HotDog runs it: odometry as `camera_init -> body`, agile gait, speed clamps       |
| `config/stack.yaml`      | per-node overrides: odometry only, the merged Airy cloud, health topics                         |
| `config/sim.yaml`        | on top of `stack.yaml` in `sim.launch.py` (dharma_sim's odometry, cloud and IMU)                |
| `launch/robot.launch.py` | the M20 driver (`m20_bringup`), the LiDARs (`hotdog_base`) and the stack                        |
| `launch/sim.launch.py`   | dharma_sim and the stack                                                                        |
| `hotdog/stack.py`        | the composition: package launch files, their arguments, the nodes they start                    |
| `hotdog/bringup.py`      | argument validation, the robot profile check, parameter file merging                            |
| `hotdog/launch_utils.py` | the launch actions shared by both launch files                                                  |

## Launch

```bash
ros2 launch hotdog robot.launch.py                                      # the whole robot
ros2 launch hotdog robot.launch.py site:=gi_cawang robot_ip:=10.21.31.103
ros2 launch hotdog robot.launch.py robot_driver:= lidar:=external        # both run elsewhere
ros2 launch hotdog sim.launch.py rviz:=true scenario:=person_crossing
```

| Argument                       | Default (env)                              |                                                                                       |
| ------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------- |
| `robot_params`                 | `config/robot.yaml`                        | robot profile file                                                                    |
| `params_file`                  | (`PARAMS_FILE`)                            | this robot and site on top of `config/stack.yaml` (e.g. `/etc/hotdog/site.yaml`)      |
| `use_sim_time` / `log_level`   | / `info`                                   |                                                                                       |
| `robot_ns`                     | `m20` (`ROBOT_NS`)                         | driver namespace: `/m20/cmd_vel`, `/m20/odom`, `/m20/imu`, `/m20/battery`             |
| `robot_driver`                 | `m20_bringup` (`ROBOT_DRIVER`)             | `<package>[/<file>.launch.py]` started with `namespace:=<robot_ns>`; empty: elsewhere |
| `robot_ip`                     | (`ROBOT_IP`)                               | the M20's UDP server; empty: `driver_params`                                          |
| `driver_params`                | `config/m20_driver.yaml` (`DRIVER_PARAMS`) | this robot's m20_driver file (calibrated speeds, angle unit)                          |
| `lidar`                        | `rslidar` (`LIDAR`)                        | `rslidar`: rslidar_sdk for both Airy; `external`: the clouds come from elsewhere      |
| `site` / `sites_dir`           | (`SITE`, `SITES_DIR`)                      | the site whose routes are used; empty: from the parameter files (or the last site)    |
| `fiducials`                    | `false`                                    | camera throttle + tag detector (needs a calibrated camera)                            |
| `camera_image` / `camera_info` |                                            | empty: the perception defaults                                                        |
| `health`                       | `true`                                     | start the health monitor                                                              |
| `world` / `scenario` / `rviz`  | / / `false`                                | simulator only                                                                        |

What the launch does:

1. Validates every argument and the robot profile (`dharma_utils.robot.RobotProfile`: unknown
   names and out-of-range values stop the launch with the reason).
2. Merges `config/stack.yaml` (+ `config/sim.yaml`) and `params_file` into one parameter file
   (later wins, parameter by parameter), adds every started node (the M20 driver's too) to the
   health monitor's `nodes.expected`, and reports sections that match no node (typos).
3. Starts `m20_bringup` with `namespace`, `driver_params` and `robot_ip`, then each package
   launch (`dharma_odometry` external, `dharma_localization`, `hotdog_base`,
   `dharma_perception`, `dharma_mapping`, `dharma_navigation`, `dharma_control`,
   `dharma_health`) in its own launch scope: no argument of this launch leaks into another.
4. The control mux is the only publisher of `/m20/cmd_vel`; navigation reads `/m20/battery`
   and `/m20/odom`.

## Odometry only

HotDog maps nothing. The M20's dead reckoning is the odometry: m20_driver publishes it as
`camera_init -> body` (`config/m20_driver.yaml`), which dharma_localization bridges into
`odom -> base_link` (`body` is `imu_link`, the identity of `base_link` in the URDF), and the
odometry start is the map origin (`assume_start_origin`). So:

- **Start at the dock.** Routes are taught and repeated relative to where the odometry
  started; the robot must start (and be re-anchored, `/localization/assume_origin`) on the
  same spot, the charging dock, every time.
- **Drift is not corrected.** Without tags or a map the error grows with distance;
  `localization/status` keeps reporting it as sigma. Keep rounds short enough, or add tags
  (`fiducials:=true` with a calibrated camera) for re-anchoring along the way.
- **A driver restart resets the odometry.** The odometry monitor reports the restart,
  localization drops to `NONE` and the follower pauses; return to the dock and call
  `/localization/assume_origin` again.

dharma_mapping still runs for the sites: each site is a folder of taught routes
(`<sites_dir>/<site>/routes/*.csv`); its grid mapper stays idle.

## Tests

`test/unit` (argument validation, parameter merging, the composition), `test/ros` (both launch
files against stub packages, and `ros2 launch --show-args` when installed), `test/test_style.py`.

```bash
colcon build --packages-select hotdog && colcon test --packages-select hotdog
```
