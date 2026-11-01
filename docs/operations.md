# Operations

Day-to-day use of HotDog on a commissioned robot and site ([commissioning](commissioning.md)).
Every command runs on the payload computer in a shell with the service's environment
(`source ~/dev/HotDog/install/setup.bash` after `source /opt/ros/foxy/setup.bash`, with
`ROS_LOCALHOST_ONLY=1` like the service).

## Start of a shift

1. The M20 sits on its dock, the payload computer is on: `sudo systemctl status hotdog`
   (it starts at boot).
2. `ros2 topic echo --once /health/status`: `level` OK (or WARN with a reason you accept).
3. `ros2 topic echo --once /inspection/status`: `pod_connected` and `acoustic_connected` true.
4. Set the air temperature of the day, the reference of the ambient criterion:
   `ros2 param set /inspection_node thermal.ambient_c 33.0`.
5. `ros2 topic echo --once /patrol/status`: `schedule_enabled` and `next_scheduled` as planned.

## Teach a route

Routes are taught from the dock and repeated from it: the dock is the origin of the map frame.

```bash
ros2 service call /localization/assume_origin std_srvs/srv/Trigger   # on the dock
ros2 service call /m20/stand_up std_srvs/srv/Trigger
ros2 service call /route/start std_srvs/srv/Trigger
```

Drive with the **M20 remote**: the control mux stays in AUTO with nothing to send, so the
driver is quiet and the remote's joystick has the robot (`/m20/state` `velocity: idle`). At
each piece of equipment:

```bash
ros2 service call /route/mark_stop_point dharma_interfaces/srv/MarkStopPoint "{dwell_sec: 5.0}"
```

then teach its targets ([below](#teach-inspection-targets)) before driving on. End next to the
dock's approach, then:

```bash
ros2 service call /route/stop std_srvs/srv/Trigger     # <site>/routes/<date>_<time>.csv
ros2 service call /m20/charge_start std_srvs/srv/Trigger
```

`ros2 topic echo --once /site/status` lists the site's routes. Drive slowly and smoothly while
teaching: the follower repeats the path as driven.

## Teach inspection targets

Standing on the stop point, aim the pod at the equipment:

```bash
ros2 service call /unipod/set_angle unipod_msgs/srv/SetGimbalAngle "{yaw: 35.0, pitch: -10.0}"
ros2 service call /unipod/set_zoom unipod_msgs/srv/SetZoom "{zoom: 4.0}"
ros2 service call /inspection/add_target hotdog_interfaces/srv/AddTarget \
  "{name: bay1_ds_clamps, thermal: true, acoustic: true, strips: 3}"
```

| Equipment                                   | Target                                                      |
| ------------------------------------------- | ----------------------------------------------------------- |
| three phases side by side (clamps, bushings) | `thermal: true, strips: 3`: the phases are compared         |
| a single joint or termination               | `thermal: true` (`max_temp_c` for an own limit)             |
| insulators, cable terminations, GIS spacers | `acoustic: true`: partial discharge detection               |

Several targets per point are fine (each is a pan, tilt and zoom). Fine-tune them in
`<sites_dir>/<site>/inspection.yaml` (regions in thermal pixels, limits, detection time); the
file is read at every inspection. Details: [hotdog_inspection](../src/hotdog_inspection/README.md).

## Patrol

From the dock, on demand:

```bash
ros2 service call /patrol/start hotdog_interfaces/srv/StartPatrol "{route: 20261101_093000}"
ros2 topic echo /patrol/status
```

or on a schedule, kept in the site file (`/etc/hotdog/site.yaml`) to survive a restart:

```yaml
patrol_node:
  ros__parameters:
    schedule:
      enabled: true
      times: ["06:00", "14:00", "22:00"]
      route: "20261101_093000"
```

A patrol checks health, battery and the e-stop, re-anchors at the dock, stands up, follows the
route, inspects at each stop point and docks again. Pause and resume:
`/navigation/pause`, `/navigation/resume`; stop: `/patrol/stop` (the robot stands where it is).

## Results

| What                         | Where                                                                       |
| ---------------------------- | --------------------------------------------------------------------------- |
| each inspection point        | `~/.hotdog/reports/<day>/<time>_<point>/report.json` and the images         |
| every finding of the day     | `~/.hotdog/reports/<day>/findings.csv`                                       |
| each patrol                  | `~/.hotdog/reports/<day>/patrol_<time>.json`: points, findings, the worst   |
| live                         | `/inspection/report`, `/patrol/status`                                       |

| Severity  | Thermal (default)                                        | Partial discharge | Act                       |
| --------- | -------------------------------------------------------- | ----------------- | ------------------------- |
| attention | ≥ 80 °C, ≥ 11 °C over ambient, ≥ 2 °C over the phases     | corona            | look again next round     |
| warning   | ≥ 90 °C, ≥ 21 °C over ambient, ≥ 4 °C over the phases     | surface           | plan a repair             |
| critical  | ≥ 105 °C, ≥ 41 °C over ambient, ≥ 16 °C over the phases   | floating          | report to the substation now |

Copy a day off the robot: `scp -r robot@<ip>:~/.hotdog/reports/<day> .`

## Emergency stop

- **Hard:** the M20's own e-stop or remote; the driver holds `cmd_vel` until `stand_up`.
- **Latched in HotDog:** `ros2 service call /control/estop/engage std_srvs/srv/Trigger`. Only
  zero velocity leaves the control mux until `/control/estop/release`; the patrol stays paused
  until `/navigation/resume` or a new `/patrol/start`.
- The protective field (both Airy, 360°) stops the robot before any obstacle on every side.

## When something goes wrong

| Symptom                                           | Cause and fix                                                                                                                                      |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `patrol/status` `FAILED` at `checks`              | `message` says which: health ERROR (`/health/status` issues), e-stop latched, battery below `start.min_battery`                                     |
| `FAILED` at `stand up`                            | the M20 is charging, on a hard e-stop or not connected: `/m20/state`                                                                               |
| the robot pauses mid-route, `localization` `NONE` | the M20 driver restarted, its odometry is reset: drive it to the dock with the remote, `/localization/assume_origin`, start the patrol again          |
| it stops short of the stop points over the round  | odometry drift: shorter routes, or tags along the way (`fiducials:=true`, a calibrated camera)                                                    |
| reports `partial`, `pod_connected: false`        | the pod's network or power: `ping $POD_IP`, `ros2 topic hz /unipod/status`                                                                         |
| `acoustic_connected: false`                       | `ping 192.168.2.204`, the password in `/etc/hotdog/hotdog.env`, the camera in partial discharge mode                                                |
| the robot does not move in AUTO                   | `/control/status` (mode, e-stop, field), `/m20/state` `velocity` (`hold`: call `stand_up`; `takeover`: the app or remote took the robot)          |

Logs: `journalctl -fu hotdog`; `scripts/setup.sh` checks every component.
