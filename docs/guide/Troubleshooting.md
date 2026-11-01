# Troubleshooting

Start with `ros2 topic echo /health/status` (or `rqt_robot_monitor`): it names the item and,
for TF, the likely cause. Then the status topics: `odometry/status`, `localization/status`,
`navigation/status`, `control/status`.

## The robot does not move

| Symptom                                                | Check                                                                                                                                   |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `control/status` `estop: true`                         | the reasons; release with `control/estop/release` (refused while the hardware e-stop is pressed), then `navigation/resume`              |
| `armed: false`                                         | the active source must send neutral commands first (re-arm); navigation re-arms by staying silent for `nav_timeout_sec`                 |
| field `STALE`                                          | `perception/safety_scan` missing, late, in the wrong frame or not 360°; is `lidar_sector_node` running and receiving the LiDAR?         |
| field `BLIND`                                          | blocked sectors: LiDAR blind or covered, TF sensor -> base or odom -> base missing, no cloud for `input.timeout_sec`                    |
| field `STOP` / `LIMITED` with nothing around           | the self filter or the height band sees the robot or the floor: `filter.self_margin`, `filter.height_min`, `robot.base_height`          |
| `navigation/status` `PAUSED`                           | the pause reasons: `estop` (resume after the release), `remote` (switch to AUTO), `localization` (not localized), `battery`, `operator` |
| status message `TF_STALE` / `TF_CLOCK` / `TF_STARTING` | the robot pose is old, from the future or missing: [TF latency](#tf-latency-diagnosis-in-ten-minutes)                                   |
| `BLOCKED`                                              | no progress: an obstacle, a blind scan or an emergency; the planner replans a `planner/go_to` goal                                      |
| `OFF_PATH`                                             | the robot is too far from the route (`safety.off_path_stop`): bring it back and start again                                             |
| start refused                                          | the robot is further than `join.max_distance` from the route, or a start hook failed                                                    |

## Localization

| Symptom                                  | Check                                                                                                           |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| stays `NONE`                             | a tag in view and in the site's `tags.json`? detector frames on TF? `localization/start`, or a 2D Pose Estimate |
| corrections rejected                     | the chi-square gate: a far tag that disagrees is refused automatically; `localization/start` applies it         |
| map tilted, floor seen as obstacles      | the odometry started tilted: `odometry/status` `DEGRADED`; restart standing still and level (`wait_still`)      |
| `odometry/status` `LOST` after a restart | expected for `hold_sec`; localization re-levels and needs a tag or a pose estimate again                        |

## Time synchronisation

Every stamp must come from one clock: the LiDAR's points, the IMU, the camera, the odometry, TF
and the events a product sends to its server. `scripts/timesync.sh` (also `scripts/setup.sh
install timesync ptp`) sets it up on a robot computer:

| Part       | What it does                                                                                                                                                                                                                 | Settings                                                                       |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `timesync` | chrony replaces systemd-timesyncd: the system clock follows the time servers and serves the robot's other computers (`local stratum 10`: also without internet). The robot's other computers point their chrony at this one. | `TIME_SERVERS` (empty: the distribution's pool), `TIME_ALLOW` (subnets served) |
| `ptp`      | `ptp4l` as PTP master (UDPv4, E2E) on the interface of the LiDAR: a Livox Mid-360 then stamps its points with this computer's clock. Hardware timestamps add `phc2sys` (the interface clock follows the system clock).       | `LIDAR_IP` / `LIVOX_IP` or `PTP_IFACE`, `PTP_TIMESTAMPING` (software)          |

`scripts/timesync.sh check` reports the offset to the time source (at most `TIME_MAX_OFFSET`,
0.05 s) and whether the PTP master runs. On the robot, health watches the same with
`clock.enabled: true` (`clock:ntp`), and a LiDAR that still runs on its own clock shows as a
sensor stamp in the future or a steady TF delay (`steady (source clock offset?)`). In a container
both are the host's job.

## TF latency: diagnosis in ten minutes

The follower stops when the robot pose (`map -> base_link`) is older than
`safety.tf_timeout_sec` (0.5 s). tf2 answers at the latest time every edge of the chain has, so
the oldest edge decides; normally the LiDAR-inertial edge `camera_init -> body` (a 100 ms scan
plus 20–80 ms of processing: 0.15–0.35 s in total).

1. **Measure the sensor clock offset.** Compare `header.stamp` of `/livox/lidar` (and
   `/livox/imu`, `/Odometry`, the camera info) with the host clock at reception, for example the
   median over 10 s. Normally 0.10–0.15 s; much more, or the year 1970, means the LiDAR runs on
   its own clock.
2. **Find the old edge.** `ros2 run tf2_ros tf2_monitor map base_link` shows the average and
   maximum delay per edge. A large and stable delay of `camera_init -> body` points to the
   clock; a fluctuating one to load. Health says the same: `steady (source clock offset?)` or
   `varying (system load?)`.
3. **Check between machines.** `chronyc tracking` on each computer: the offset must be below
   1 ms on a LAN (`clock.enabled: true` lets health watch it).
4. **Check the load.** `tegrastats` (Jetson), `ros2 topic hz /tf`, `ros2 topic bw /tf`.
5. **Repeat standing still and driving.** A constant offset is a clock problem, an age that grows
   while moving is load.

| Cause                             | Fix                                                                                                                                                   |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| LiDAR clock not synchronized      | `scripts/setup.sh install ptp`: `ptp4l` as PTP master on the LiDAR's interface (see below); without PTP, restamp in the driver with a nominal latency |
| two computers' clocks differ      | `scripts/setup.sh install timesync` on each: chrony, one computer serving the others (see below)                                                      |
| CPU load or thermal throttling    | fewer or lighter nodes, `/tf` load down (joint states at most 30 Hz or on their own topic), real-time priority for the estimator                      |
| an edge stops for a while         | estimator start (the still gate holds it) or respawn; `odometry/status`                                                                               |
| mixed `use_sim_time`              | only in simulation or bag replay: `ros2 param get <node> use_sim_time` for every node                                                                 |
| camera stamps on the device clock | let the driver use the host clock (RealSense: global time)                                                                                            |

The manual's health chapter has the latency budget in detail.

## Build and launch

| Symptom                               | Check                                                                                                 |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `colcon test-result` reports 0 tests  | the package needs `extras_require={'test': ['pytest']}`                                               |
| a node refuses to start               | the log names the parameter and why (range, cross-field check, unknown controller or policy)          |
| the launch stops on the robot profile | unknown names or out-of-range values in `robot.yaml`                                                  |
| `ros2 param set` rejected             | out of range, or read-only at runtime (safety values): change the file and restart                    |
| `livox_ros_driver2` missing           | perception publishes BLOCKED scans; build the external repos (`scripts/setup.sh install livox repos`) |
