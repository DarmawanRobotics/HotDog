# Operations

Day-to-day use of HotDog on a commissioned robot and site ([commissioning](commissioning.md)).
Log in to the payload computer (`ssh robot@<ip>`) and use the **`hotdog`** command
(`hotdog help` lists everything; `scripts/setup.sh install cli` creates it). Each one is a
plain ROS 2 call underneath ([scripts/hotdog.sh](../scripts/hotdog.sh)); in a shell with
`source ~/dev/HotDog/scripts/env.sh` every topic and service of the stack is reachable too.

## Start of a shift

1. The M20 sits on its dock, the payload computer is on (HotDog starts at boot).
2. `hotdog status`:

   ```
   patrol      IDLE  points 0 (C0 W0 A0) next 14:00
   health      OK  speed 100%
   localize    LOCALIZED  (odometry) drift ±0.00 m
   control     AUTO  e-stop off field CLEAR
   battery     96%
   inspection  IDLE  pod ok acoustic ok ambient 30.0 °C 12 points 30 targets
   navigation  INACTIVE
   alerts      nothing waiting
   reports     http://10.21.31.50:8088/
   ```

   health OK (or WARN with a reason you accept), pod and acoustic ok, the schedule as planned.

3. The air temperature of the day, the reference of the ambient criterion: `hotdog ambient 33`.

## Teach a route

Routes are taught from the dock and repeated from it: the dock is the origin of the map frame.

```bash
hotdog stand            # on the dock
hotdog teach start      # the dock becomes the origin, recording starts
```

Drive with the **M20 remote**: the control mux stays in AUTO with nothing to send, so the
driver is quiet and the remote's joystick has the robot (`/m20/state` `velocity: idle`). At
each piece of equipment:

```bash
hotdog teach point      # a stop point here (hotdog teach point 8: dwell 8 s)
```

then teach its targets ([below](#teach-inspection-targets)) before driving on. End next to the
dock's approach, then:

```bash
hotdog teach stop       # <site>/routes/<YYYY-MM-DD_HH-MM-SS>.csv
hotdog dock
```

`hotdog routes` lists the site's routes. Drive slowly and smoothly while
teaching: the follower repeats the path as driven.

## Teach inspection targets

Standing on the stop point, aim the pod at the equipment:

```bash
ros2 service call /unipod/set_angle unipod_msgs/srv/SetGimbalAngle "{yaw: 35.0, pitch: -10.0}"
ros2 service call /unipod/set_zoom unipod_msgs/srv/SetZoom "{zoom: 4.0}"
hotdog teach target bay1_ds_clamps strips=3 acoustic
```

| Equipment                                    | Target                                                         |
| -------------------------------------------- | -------------------------------------------------------------- |
| three phases side by side (clamps, bushings) | `hotdog teach target <name> strips=3`: the phases are compared |
| a single joint or termination                | `hotdog teach target <name>` (`max=95` for an own limit)       |
| insulators, cable terminations, GIS spacers  | `hotdog teach target <name> acoustic`: partial discharge       |

Several targets per point are fine (each is a pan, tilt and zoom). Fine-tune them in
`<sites_dir>/<site>/inspection.yaml` (regions in thermal pixels, limits, detection time); the
file is read at every inspection. Details: [hotdog_inspection](../src/hotdog_inspection/README.md).

## Patrol

From the dock, on demand:

```bash
hotdog patrol 2026-11-01_09-30-00     # or just `hotdog patrol`: the route patrolled last
hotdog status
```

or on a schedule, kept in the site file (`/etc/hotdog/site.yaml`) to survive a restart:

```yaml
patrol_node:
  ros__parameters:
    schedule:
      enabled: true
      times: ["06:00", "14:00", "22:00"]
      route: "2026-11-01_09-30-00"
```

A patrol checks health, battery and the e-stop, re-anchors at the dock, stands up, follows the
route, inspects at each stop point and docks again. `hotdog pause` / `hotdog resume`;
`hotdog stop` stops it where the robot stands. `hotdog schedule on | off | show`.

**Back to the dock** at any time: `hotdog return`. The
robot walks the taught route backwards (no inspections) and docks. The watchdog does the same
on its own below 20 % battery, after 2 h or when the robot is blocked for 3 min; off the route,
lost or with a silent follower it stops instead and the patrol ends `FAILED`. An operator
pause, the e-stop or REMOTE is never overruled.

## Results

Open **`http://<robot>:8088/`** in a browser on the substation network: every day, each patrol
as a page with its points, findings, the change since the last round and the thermal, visible
and sound map images (print it to PDF from the browser). The files behind it:

| What                     | Where                                                                     |
| ------------------------ | ------------------------------------------------------------------------- |
| each inspection point    | `~/.hotdog/reports/<day>/<time>_<point>/report.json` and the images       |
| every finding of the day | `~/.hotdog/reports/<day>/findings.csv`                                    |
| each patrol              | `~/.hotdog/reports/<day>/patrol_<time>.json`: points, findings, the worst |
| each patrol's page       | `~/.hotdog/reports/<day>/patrol_<time>.html`                              |
| live                     | `/inspection/report`, `/patrol/status`                                    |

| Severity  | Thermal (default)                                       | Partial discharge | Act                          |
| --------- | ------------------------------------------------------- | ----------------- | ---------------------------- |
| attention | ≥ 80 °C, ≥ 11 °C over ambient, ≥ 2 °C over the phases   | corona            | look again next round        |
| warning   | ≥ 90 °C, ≥ 21 °C over ambient, ≥ 4 °C over the phases   | surface           | plan a repair                |
| critical  | ≥ 105 °C, ≥ 41 °C over ambient, ≥ 16 °C over the phases | floating          | report to the substation now |

Copy a day off the robot with its images: `scp -r robot@<ip>:~/.hotdog/reports/<day> .`.
Days older than a year, and the oldest days when less than 5 GB is free, are deleted on the
robot ([hotdog_reports](../src/hotdog_reports/README.md#retention)).

## Alerts

The crew's Telegram group gets every **warning** and **critical** finding with its thermal
image or sound map, every patrol that failed or came back on its own, every finished patrol
with a link to its report, and a robot whose health is ERROR. Act on the last line of a
finding alert; a repeated finding stays quiet for 12 h unless it gets worse. Without uplink
the alerts wait on the robot and arrive when the link is back.

## Emergency stop

- **Hard:** the M20's own e-stop or remote; the driver holds `cmd_vel` until `stand_up`.
- **Latched in HotDog:** `hotdog estop`. Only zero velocity leaves the control mux until
  `hotdog release`; the patrol stays paused until `hotdog resume` or a new `hotdog patrol`.
- The protective field (both Airy, 360°) stops the robot before any obstacle on every side.

## When something goes wrong

| Symptom                                           | Cause and fix                                                                                                                                |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `patrol/status` `FAILED` at `checks`              | `message` says which: health ERROR (`/health/status` issues), e-stop latched, battery below `start.min_battery`                              |
| `FAILED` at `stand up`                            | the M20 is charging, on a hard e-stop or not connected: `/m20/state`                                                                         |
| the robot pauses mid-route, `localization` `NONE` | the M20 driver restarted, its odometry is reset: drive it to the dock with the remote, `/localization/assume_origin`, start the patrol again |
| `FAILED`, `returned: true`                        | the watchdog brought it back (battery, duration, blocked): the `message` says which; the reports of the points done are kept                 |
| `FAILED`: `no way back`                           | the robot had no pose or the route file is gone: drive it to the dock with the remote                                                        |
| it stops short of the stop points over the round  | odometry drift: shorter routes, or tags along the way (`fiducials:=true`, a calibrated camera)                                               |
| reports `partial`, `pod_connected: false`         | the pod's network or power: `ping $POD_IP`, `ros2 topic hz /unipod/status`                                                                   |
| `acoustic_connected: false`                       | `ping 192.168.2.204`, the password in `/etc/hotdog/hotdog.env`, the camera in partial discharge mode                                         |
| the robot does not move in AUTO                   | `/control/status` (mode, e-stop, field), `/m20/state` `velocity` (`hold`: call `stand_up`; `takeover`: the app or remote took the robot)     |

Logs: `hotdog logs`; `scripts/setup.sh` checks every component; `hotdog restart` restarts the
service (ROS logs older than 7 days are deleted at each start).
