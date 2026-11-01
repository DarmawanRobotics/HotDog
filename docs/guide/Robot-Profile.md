# Robot Profile

The robot profile is the one description of the robot that every Dharma node reads
(`dharma_utils.robot.RobotProfile`). A product passes it to every node from one file, usually
`config/robot.yaml` of its bringup package:

```yaml
/**:
  ros__parameters:
    robot:
      name: robot # model, for logs
      kinematics: omni # omni: vx, vy, wz (legged, mecanum); diff: vx, wz (max_vy must be 0)
      base_height: 0.35 # m, base_link above the floor when standing
      footprint: # m, base_link to the edges (x forward, y left)
        front: 0.40
        rear: 0.40
        half_width: 0.28
      limits:
        max_vx: 0.8 # m/s
        max_vy: 0.4 # m/s
        max_wz: 1.0 # rad/s
        max_accel: 0.5 # m/s^2
        max_decel: 0.6 # m/s^2, braking
        max_yaw_accel: 1.5 # rad/s^2
        reaction_time: 0.25 # s, command to braking (sensing + transport)
      frames:
        map: map
        odom: odom
        base: base_link
```

The bringup validates it at launch (unknown names and out-of-range values stop the launch with
the reason) and every node validates it again; `ros2 param describe /<node> robot.limits.max_vx`
shows the unit and range. `max_vy` must be 0 for `diff` robots and the three frames must differ.

## What is derived from it

| Quantity             | Formula                                            | Used by                                                   |
| -------------------- | -------------------------------------------------- | --------------------------------------------------------- |
| inscribed radius     | `min(front, rear, half_width)`                     | planner lethal radius (+ margin)                          |
| circumscribed radius | `sqrt(max(front, rear)^2 + half_width^2)`          | oriented footprint checks, the ring swept when turning    |
| floor                | `base_link` minus `base_height`                    | height bands of perception and mapping, scan matching     |
| lateral speed        | `vy = 0` for `diff`                                | envelope, controllers, approach                           |
| stopping distance    | `D(v) = v * reaction_time + v^2 / (2 * max_decel)` | speed profile, path shift, motion guard, protective field |
| jump limits          | `max_vx`, `max_wz`                                 | odometry monitor, mapping jump gate                       |

With the default footprint the inscribed radius is 0.28 m and the circumscribed radius 0.49 m:
a planner that used one radius of 0.35 m (Dharma 0.1) could bring a corner of the body into a
wall in a narrow corridor.

## Measure the braking limits

`max_decel`, `max_yaw_accel` and `reaction_time` bound every speed limit in the stack. The
defaults are placeholders: measure them on the robot, in the worst case (slippery floor, full
payload, low battery), before it drives on its own. The hub has a tool for it,
`docs/manual/tools/brake_test.py`:

1. Open, flat area of at least three stopping distances; people kept away; hardware e-stop at
   hand; bringup running with the default limits.
2. Put the mux in REMOTE:
   `ros2 service call /control/set_mode dharma_interfaces/srv/SetMode "{mode: remote, source: dashboard}"`.
3. Record at least three runs per speed, up to `max_vx`, and the same for yaw up to `max_wz`:
   ```bash
   python3 brake_test.py drive --speed 0.5 --odom /<ns>/odom --out lin_0.5_1.csv
   python3 brake_test.py drive --axis angular --speed 1.0 --odom /<ns>/odom --out yaw_1.0_1.csv
   ```
4. `python3 brake_test.py analyze lin_*.csv` prints per run the speed before the step, the
   reaction time, the deceleration and the measured and modelled stopping distance, then the
   worst values.
5. Set `max_decel` / `max_yaw_accel` to the smallest measured deceleration and `reaction_time`
   to the largest measured reaction **plus** the sensing delay the test does not see (the mean
   of `ros2 topic delay /perception/safety_scan` and one LiDAR frame period), then add margin.
6. Repeat the fastest runs with the new values: every measured stopping distance must stay
   below `D(v)`.

`brake_test.py demo` produces runs of the simulator's body model with known values, to check the
analysis. The manual (chapter 3) has the full procedure and an example.

## Frames

`robot.frames` names the map, odom and base frames for every node. The LiDAR-inertial frames
(`camera_init`, `body`) and the sensor frames are parameters of localization and perception;
the sensor mounts come from the robot's URDF.
