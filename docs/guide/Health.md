# Health

`dharma_health` turns the state of the robot into one typed signal. `health_monitor_node` runs
every check each second and publishes:

- `health/status` (`HealthStatus`, latched): `level` (`OK`, `WARN`, `ERROR`), `issues` (one line
  per problem, errors first) and `speed_scale` (0..1);
- `diagnostics` (`DiagnosticArray`): one status per checked item, `health: <item>`, for
  `rqt_robot_monitor`. Items stay listed when they recover.

```bash
ros2 topic echo /health/status
ros2 run rqt_robot_monitor rqt_robot_monitor
```

## Checks

| Item                   | WARN                                                                                   | ERROR                                    |
| ---------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------- |
| `sensor:<topic>`       | not published; slower than 80 % of its minimum rate; stamps too old or from the future |                                          |
| `state:odometry`       | `INITIALIZING`, `DEGRADED`; no or stale status                                         | `LOST`                                   |
| `state:localization`   | `NONE`, `UNCERTAIN`; no or stale status                                                |                                          |
| `state:control`        | no or stale status                                                                     | e-stop engaged; field `STALE` or `BLIND` |
| `state:safety_scan`    | some sectors blocked; none received during the start-up grace                          | stale; blind (every sector blocked)      |
| `node:/<ns>/<name>`    | not running yet (start-up grace); running twice                                        | not running                              |
| `tf:<parent>-><child>` | late (cause clock, load or stopped), ahead of the clock, gone; a required edge missing |                                          |
| `system:*`             | temperature, memory, disk, load, CPU, Jetson GPU over the limit; **unreadable**        |                                          |
| `clock:ntp` (optional) | `chronyc tracking` offset above the limit, not synchronized, command failed            |                                          |

- **Stamps, not only rates.** Topics are subscribed raw and the header stamp is read from the
  serialized bytes (a point cloud is never deserialized). A 10 Hz topic with 2 s old stamps is
  late.
- **TF diagnosis.** Each dynamic edge keeps its ages over a window. Late but steady ages mean a
  clock offset of the source (`camera_init->body 1.8 s old, steady (source clock offset?)`),
  varying ages mean load, a stamp that stops advancing a stopped publisher. See
  [Troubleshooting](Troubleshooting.md).
- **Clock.** `clock:ntp` runs with `clock.enabled: true`, which the template's
  `config/stack.yaml` sets on the robot (`sim.yaml` turns it off). It needs chrony:
  `scripts/setup.sh install timesync` (and `ptp` for the LiDAR), see
  [Time synchronisation](Troubleshooting.md#time-synchronisation).
- **Thermal zones** are read only when their type matches `system.thermal_zones` (CPU, GPU,
  junction, x86 package): some Jetson zones report bogus values.
- **Nodes** are named fully qualified (`/robot/control_mux_node`); the bringup adds every node it
  starts to `nodes.expected`.

## Speed scale

`speed_scale` is the lowest scale any finding asks for: an error asks for 0, a warning for the
lowest matching `degradation.rules` entry or `degradation.warn_scale` (1). The defaults halve the
speed while the LiDAR or the estimator is slow or late, or a TF edge is late:

```yaml
health_monitor_node:
  ros__parameters:
    degradation:
      rules: ["sensor:/livox/lidar=0.5", "sensor:/Odometry=0.5", "tf:*=0.5"]
```

The control mux applies it with `use_health_limit: true`; a health status older than
`health_timeout_sec` is ignored. Health is a diagnostic aid, not a safety function: the
protective field and the e-stop never depend on it.

## Configure

The product sets what to watch, e.g. in its stack file:

```yaml
health_monitor_node:
  ros__parameters:
    sensors:
      topics: ["/livox/lidar:5.0", "/Odometry:8.0", "/camera/color/camera_info:10.0:0.3"]
    tf:
      edges: ["camera_init->body"]
    clock:
      enabled: true
```

`topic:min_hz[:max_age_sec]` (max_age_sec 0: no stamp check). Do not list a camera image topic:
a raw subscription makes the driver encode every frame. Products add checks without forking: a
`Check` subclass registered in the `dharma_health.checks` entry point group and named in
`extra_checks`.
