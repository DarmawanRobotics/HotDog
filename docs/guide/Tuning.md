# Tuning

Every Dharma parameter is typed: it has a description, a unit and a range, it is validated when
the node starts and on every `ros2 param set`, and an invalid value is rejected with the reason.
Safety values (limits, margins, timeouts) are **read-only at runtime**: change them in the
parameter file and restart.

```bash
ros2 param describe /path_follower_node speed.cruise      # description, unit, range, read-only
ros2 param set /path_follower_node speed.cruise 0.5
ros2 param dump /path_follower_node > follower.yaml
```

## The Tuning panel

In RViz (_Panels → Add New Panel → dharma_rviz/TuningPanel_): pick a node, **Load**, edit, then
**Apply** (_Apply on change_ is off by default; the mouse wheel changes a value only when the box
has focus). Ranges come from the node's descriptors, read-only parameters are disabled, and
`controller` / `policy` show only the section of the selected implementation. **Save YAML**
writes every shown value at full precision, ready for the product's parameter file.

## Where the values go

Parameters are applied in this order, later wins:

1. the package defaults (`config/<pkg>.yaml`, only what differs from the code);
2. the robot profile (`robot_params`, e.g. `config/robot.yaml` of the bringup);
3. the product's stack file (`config/stack.yaml`, per node) and `params_file`;
4. non-empty launch arguments (an empty argument never overrides a file).

The bringup reports sections that match no node (typos), and every node reports parameters it
does not declare.

## What to tune first

| Order | What                     | Parameters                                                                                                                                                       |
| ----- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | the robot profile        | footprint, `base_height`, speed limits; **measure** `max_decel`, `max_yaw_accel`, `reaction_time` ([Robot Profile](Robot-Profile.md#measure-the-braking-limits)) |
| 2     | perception height band   | `lidar_sector_node`: `filter.height_min` / `height_max` (floor not seen, low obstacles seen), `filter.self_margin`                                               |
| 3     | protective field margins | `control_mux_node`: `field.margin`, `field.remote_margin`, `field.lateral_margin`, `field.yaw_margin`                                                            |
| 4     | follower speed           | `path_follower_node`: `speed.cruise`, `speed.approach_speed`, `speed.lateral_accel`                                                                              |
| 5     | passing obstacles        | `avoidance_mode`; `path_shift.max_offset`, `path_shift.clearance`; or the avoidance node's `policy` and `shared.safe_distance`                                   |
| 6     | controller               | `controller` and its `<name>.*` section                                                                                                                          |
| 7     | localization noise       | `localization_node`: `estimator.sigma_xy_per_sqrt_m`, the yaw noise, `tag.max_distance_m`                                                                        |
| 8     | health                   | `health_monitor_node`: `sensors.topics`, `nodes.expected`, `degradation.rules`                                                                                   |

Tune on the simulator first ([Simulation](Simulation.md)), then on the robot slowly, in an open
area, with someone at the e-stop. The manual lists every parameter of every node with its
default, unit and range.
