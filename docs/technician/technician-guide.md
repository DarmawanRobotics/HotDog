---
title: Technician Guide
header: HotDog Technician Guide
subtitle: Configuration, tuning and maintenance of HotDog on the Lynx M20
version: "1.0"
date: 2026-11-01
audience: >-
  For the technician who commissions, tunes and maintains the robot: shell, YAML and ROS 2
  basics assumed.
note: >-
  The first bring-up of a robot and a site, step by step, is in docs/commissioning.md; the
  operators' tasks in the HotDog User Manual. This guide explains what each setting does, how
  to change it for good, and how to keep the robot fit. The parameter reference at the end is
  generated from the packages' config files.
revisions:
  - ["1.0", "2026-11-01", "First version"]
---

# How configuration works

## Where a value comes from

Every node reads its parameters in layers; a later layer wins, parameter by parameter:

| Layer                         | File                                            | Holds                                      |
| ----------------------------- | ----------------------------------------------- | ------------------------------------------ |
| package defaults              | `src/<package>/config/*.yaml`                   | what every HotDog has                      |
| robot profile                 | `src/hotdog/config/robot.yaml` (`robot_params`) | the M20: footprint, height, limits, frames |
| the stack as tuned for HotDog | `src/hotdog/config/stack.yaml`                  | odometry only, the merged cloud, the hooks |
| **this robot and site**       | `/etc/hotdog/site.yaml` (`PARAMS_FILE`)         | what you tune: the only file you edit      |
| launch arguments              | `/etc/hotdog/hotdog.env`                        | addresses, the site, secrets, what runs    |

The repository files are never edited on a robot: an update would undo the change or conflict
with it. Everything this robot and this substation need goes into `/etc/hotdog/site.yaml`,
under the node it belongs to, and survives updates.

## The env file

`/etc/hotdog/hotdog.env` is read by the service and by `scripts/env.sh` (the `hotdog`
command). No comments after a value; quotes around values with spaces.

| Variable                                           | Meaning                                                             |
| -------------------------------------------------- | ------------------------------------------------------------------- |
| `ROBOT_IP`                                         | the M20's UDP server (`10.21.31.103`)                               |
| `DRIVER_PARAMS`                                    | this robot's m20_driver calibration (`/etc/hotdog/m20_driver.yaml`) |
| `PARAMS_FILE`                                      | this robot and site (`/etc/hotdog/site.yaml`)                       |
| `ROBOT_PARAMS`                                     | this robot's profile when it differs (`/etc/hotdog/robot.yaml`)     |
| `SITE`, `SITES_DIR`                                | the site to load; where the sites live (`~/.hotdog/sites`)          |
| `POD_IP`                                           | the UniPod MT11                                                     |
| `HERTZINO_PASSWORD`                                | the acoustic camera's password                                      |
| `TELEGRAM_BOT_TOKEN`                               | the alert bot                                                       |
| `HOTDOG_WEBHOOK_TOKEN`                             | bearer of the webhook                                               |
| `INSPECTION`, `PATROL`, `REPORTS`, `ALERTS`, `POD` | `false` leaves that part out (default `true`)                       |
| `LIDAR`                                            | `rslidar` (both Airy) or `external` (clouds published elsewhere)    |
| `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION`              | `0`, `rmw_fastrtps_cpp`                                             |

The file is mode 640: it holds secrets. After a change: `hotdog restart`.

## The site file

```yaml
# /etc/hotdog/site.yaml: GI Cawang, HotDog 01
path_follower_node:
  ros__parameters:
    speed.cruise: 0.4
inspection_node:
  ros__parameters:
    thermal:
      ambient_c: 31.0
patrol_node:
  ros__parameters:
    schedule:
      enabled: true
      times: ["06:00", "14:00", "22:00"]
      route: "2026-11-01_09-30-00"
report_node:
  ros__parameters:
    title: GI Cawang 150 kV
    robot_name: HotDog 01
alert_node:
  ros__parameters:
    robot_name: HotDog 01 - GI Cawang
    language: id
    report_url: http://10.21.31.50:8088/
    telegram:
      chat_ids: ["-1001234567890"]
```

At start the bringup merges the layers, reports a section that matches no node (a typo) and
refuses values out of range with the reason; check `hotdog logs` after every change.

## Try a value live, then keep it

Most parameters are live:

```bash
source ~/dev/HotDog/scripts/env.sh
ros2 param describe /path_follower_node speed.cruise    # unit, range, live or not
ros2 param set /path_follower_node speed.cruise 0.35
```

A live change is lost at the next restart: write the value you settled on into the site file.
A parameter marked read-only needs the site file and `hotdog restart`.

# The M20

## The driver and its calibration

`m20_driver` talks to the M20's UDP server and turns `cmd_vel` into axis commands. Its own
README has the verification on the real robot: the angle unit, standing, the emergency stop,
the takeover by the remote, the speed calibration per gait, the signs of turning and strafing.
Do it once per robot and keep the result in a copy of the bringup's driver file:

```bash
sudo install -D -m 644 ~/dev/HotDog/src/hotdog/config/m20_driver.yaml /etc/hotdog/m20_driver.yaml
sudoedit /etc/hotdog/m20_driver.yaml      # angle_unit, full_scale.<gait>.*, invert_*
```

Keep `odom_frame: camera_init`, `base_frame: body` and `publish_tf: true`: they make the M20's
odometry HotDog's odometry. HotDog patrols in the agile flat gait (`stand_up_gait`).

## The robot profile and braking

`src/hotdog/config/robot.yaml` describes the M20 for every node: the footprint (body, legs and
wheels, **with the payload mounted**), `base_height`, the speed and acceleration limits and the
braking. The protective field, the planner's clearance and the LiDAR self filter follow from
it. A robot whose payload sticks out further needs its own profile: copy the file to
`/etc/hotdog/robot.yaml`, change it, and name it in the env file (`ROBOT_PARAMS`).

`max_decel` and `reaction_time` decide how early the robot brakes for an obstacle. **Measure
them** (the Dharma hub's Robot Profile guide): drive at full patrol speed on the site's ground,
stop, measure the distance. Keep `max_decel` at or below the measured deceleration and
`reaction_time` at or above the measured delay. Gravel and wet concrete brake worse than the
workshop floor.

## Odometry only

HotDog maps nothing. The M20's dead reckoning is the odometry and the odometry start is the
map origin: the dock.

- **Drift.** The error grows with the distance walked; `localization/status` reports it as
  `sigma_xy` (`hotdog status`: drift). Check on the first patrols of a route that the robot
  stops where the stop points were taught; split routes that end up too far off.
- **Re-anchoring.** Every patrol starts with `localization/assume_origin` at the dock
  (`patrol_node` `start.reanchor`). A robot moved by hand must be put back on the dock and
  re-anchored (`hotdog anchor`).
- **A driver restart resets the odometry.** The odometry monitor reports it, localization
  drops to NONE, the follower pauses and the watchdog stops the patrol after
  `abort.hold_timeout_sec`.
- **Tags** along a long route correct the drift: `fiducials:=true` with a calibrated camera
  and AprilTags recorded on the site (dharma_localization). Without them, keep routes short.

# LiDARs and the protective field

## The Airy

`rslidar_sdk` runs both RoboSense Airy from `src/hotdog_base/config/rslidar.yaml`: the front
one on UDP 6699/7788, the rear one on 6698/7789, stamped on arrival (no PTP needed).
`cloud_merger_node` merges them into `/lidar/points` in `base_link`: each input transformed by
the URDF plus `input_rpy_deg`, the robot's own body removed (footprint, `self_height` for the
pod and rails), leveled with the M20's IMU, cut to `range_max` and `height_max`. A stale input
stops the merged cloud (`require_all`): perception then reports BLOCKED and the robot stops
instead of driving half blind.

Check after mounting or replacing a LiDAR: in RViz the rear cloud lies behind the robot model
and the ground stays flat at `-base_height` while the body tilts; else fix `input_rpy_deg` in
the site file.

## What counts as an obstacle

`lidar_sector_node` turns the merged cloud into 360° sectors between `filter.height_min`
(0.15 m: gravel, kerbs, trench covers stay out) and `filter.height_max` (1.6 m) above the
ground. Lower objects, pits and drops are not seen: the route must not need it.

## The protective field

`control_mux_node` is the only publisher of `/m20/cmd_vel`. For every command it checks the
360° scan along the direction of motion with the footprint and the braking model: it slows
the robot down (field LIMITED) and stops it (field STOP) so that it can always stop before the
nearest obstacle. A stale or blind scan stops it too. The health monitor's speed limit and the
latched e-stop apply to every source.

**Test it** after every change of the profile or the LiDARs, in an open area, at patrol
speed: a person walks slowly towards the robot from the front, the back and each side; the
robot must stop before them every time.

# Patrols and the watchdog

## Speed and stop points

| Parameter (node)                                      | Default | Effect                                                    |
| ----------------------------------------------------- | ------- | --------------------------------------------------------- |
| `speed.cruise` (`path_follower_node`)                 | 0.5     | m/s along the route; 0.3 for the first patrols of a route |
| `hooks.inspection_timeout_sec` (`path_follower_node`) | 180     | s the robot waits at most for the inspection of a stop    |
| `max_duration_sec` (`inspection_node`)                | 150     | s for all targets of a point; keep below the hook timeout |
| `match_radius_m` (`inspection_node`)                  | 1.5     | m, a stop this close to an inspection point inspects it   |

A stop point waits its dwell (taught, default 5 s) plus the inspection. Each target takes the
gimbal settle time (2.5 s), the thermal samples and, with `acoustic`, the detection time (5 s).

## The watchdog

`patrol_node` `abort.*`, every second while a patrol runs:

| Parameter                    | Default  | When exceeded                                                        |
| ---------------------------- | -------- | -------------------------------------------------------------------- |
| `min_battery`                | 0.2      | back to the dock; keep above the follower's `critical_battery` (0.1) |
| `max_duration_min`           | 120      | back to the dock; set it to about twice the route's duration         |
| `hold_timeout_sec`           | 180      | blocked: back to the dock; off the route or lost: stop               |
| `nav_timeout_sec`            | 5        | the follower is silent: stop                                         |
| `return_to_dock`             | true     | false: every watchdog action stops the robot instead                 |
| `near_m`, `dock_clearance_m` | 2.0, 1.0 | where the way back starts and how far before the dock it ends        |

An operator pause, the e-stop or REMOTE is never overruled. The way back is the taught route,
reversed from the earliest waypoint near the robot, without stop points, into
`<site>/patrol/return.csv`; then `charge_start` docks the M20.

## The schedule

`schedule.enabled`, `schedule.times` (local time of the robot computer, `HH:MM`),
`schedule.route` (empty: the route patrolled last) and `schedule.window_min` (a time missed by
more than this is skipped). Keep them in the site file; operators switch the schedule on and
off with `hotdog schedule`. The robot computer's time zone must be the substation's
(`timedatectl`).

# Thermal inspection

## The pod

`unipod_driver` runs the UniPod MT11 in the `/unipod` namespace (`POD_IP`). `inspection_node`
points it with `set_angle` and `set_zoom`, waits `pod.settle_sec`, refreshes the flat-field
correction once per point (`thermal.refresh_shutter`) and asks the temperatures of boxes in
thermal pixels. With the camera's AI super-resolution on, the thermal frame is 1280 × 1024:
set `thermal.width` and `thermal.height` to match.

The MT11 gives temperatures per point, box and frame, not a radiometric image: the reports
show the camera's colour picture as evidence, and the values come from the box measurements.

## Targets in the inspection file

The operators teach targets with `hotdog teach target`; refine them in
`<sites_dir>/<site>/inspection.yaml` (read at every inspection, no restart):

```yaml
points:
  - name: bay1_disconnector
    x: 12.40
    y: -3.10
    targets:
      - name: bay1_ct_terminals
        pan_deg: -20.0
        tilt_deg: 5.0
        zoom: 2.0
        thermal:
          regions: # boxes in thermal pixels, compared with each other
            - { name: r, box: [80, 120, 200, 260] }
            - { name: s, box: [260, 120, 380, 260] }
            - { name: t, box: [440, 120, 560, 260] }
          max_temp_c: 95.0 # this part's own critical limit
        acoustic: { enabled: true, duration_sec: 8.0 }
```

Regions are better than strips when the phases are not evenly spread across the picture or
other equipment shares the frame. Find the boxes on a thermal snapshot of the target (its
report folder) at its zoom.

## Limits

`thermal.absolute`, `thermal.ambient`, `thermal.similar` each hold `attention`, `warning` and
`critical` in °C. The defaults follow the usual infrared inspection practice (NETA MTS):

| Criterion | Value judged                                     | attention / warning / critical |
| --------- | ------------------------------------------------ | ------------------------------ |
| absolute  | the hottest temperature                          | 80 / 90 / 105 °C               |
| ambient   | the hottest temperature over `thermal.ambient_c` | 11 / 21 / 41 °C                |
| similar   | the hottest region over the median of the others | 2 / 4 / 16 °C                  |

Use the substation owner's limits where they exist, and the equipment makers' limits for
parts with their own (`max_temp_c`). Readings depend on the load: note in the site's records
that limits were set for the usual load, and read rises over ambient with the load of the day.

`thermal.ambient_c` is live; operators set it every shift (`hotdog ambient`).

# Partial discharge

## The camera

The HZ-FA-371 is driven over its HTTP API (manual V5.1) by `inspection_node`; its ROS driver
is ROS 1 only. Set up on the camera's web page once: **partial discharge mode** (gas leak mode
is refused), the analysis band and the imaging threshold the manual gives for HV equipment.
`acoustic.host` (factory `192.168.2.204`), `acoustic.port`, `acoustic.user`; the password only
in the env file (`HERTZINO_PASSWORD`).

## One detection

For each acoustic target, after the robot stopped: a detection already running is stopped,
the newest record noted, a detection of `duration_sec` started, the record appearing a whole
detection later taken (an older one never), the detection stopped, the sound map and PRPD
photos saved next to the report.

## Severities

| Type     | Default   | Parameter           |
| -------- | --------- | ------------------- |
| noise    | normal    |                     |
| corona   | attention | `acoustic.corona`   |
| surface  | warning   | `acoustic.surface`  |
| floating | critical  | `acoustic.floating` |

`acoustic.intensity_warning` and `intensity_critical` raise the severity by the sound map's
intensity once the site's levels are known (0: off): record a few rounds first, then set them
above the usual levels of healthy equipment.

# Reports and alerts

## Reports

`report_node` renders a page per patrol, a page per day and a front page, and serves
`~/.hotdog/reports` read-only on `server.port` (8088). `title` and `robot_name` name the site
and the robot on every page. Retention: days older than `retention.days` (365), then the oldest
days while less than `retention.min_free_gb` (5 GB) is free; never today. `reports/rebuild`
renders every page again (after changing the title).

Keep what must be archived elsewhere: copy the day folders off the robot (with their images),
e.g. weekly with `rsync -a robot@<ip>:.hotdog/reports/ <archive>/`.

## Alerts

`alert_node` sends to the Telegram chats in `telegram.chat_ids` (the bot token in
`TELEGRAM_BOT_TOKEN`) and to `webhook.url`. Set up a bot: [@BotFather](https://t.me/BotFather),
add it to the crew's group, send a message there, read the group id (negative) from
`https://api.telegram.org/bot<token>/getUpdates`. `language: id` writes the alerts in Bahasa
Indonesia; `report_url` adds the link to the patrol page; `findings.min_severity` (warning) and
`findings.repeat_hours` (12) decide what is sent. Alerts are spooled in `~/.hotdog/alerts` and
sent every `retry_sec` until delivered, for `max_age_hours`.

The robot computer needs outbound HTTPS to `api.telegram.org`; a proxy goes into the env file
(`HTTPS_PROXY=...`).

# Network, time and the service

## Addresses and ports

| Device / service            | Address (default)                        | Port                     |
| --------------------------- | ---------------------------------------- | ------------------------ |
| Lynx M20                    | `10.21.31.103`                           | UDP 30000                |
| RoboSense Airy front / rear | send to the payload computer             | UDP 6699/7788, 6698/7789 |
| UniPod MT11                 | `10.21.31.26` (factory `192.168.144.25`) | TCP 37260, RTSP 8554     |
| Hertzinno HZ-FA-371         | `192.168.2.204` (factory)                | HTTP 80                  |
| report server               | the payload computer                     | TCP 8088                 |
| SSH                         | the payload computer                     | TCP 22                   |

The payload computer needs an address in each subnet (netplan, docs/commissioning.md). ROS 2
runs with `rmw_fastrtps_cpp` on domain 0.

## Service commands

```bash
sudo systemctl status hotdog          # running? since when?
hotdog logs                           # journalctl -fu hotdog
hotdog restart                        # sudo systemctl restart hotdog
scripts/setup.sh                      # every component: ok or missing
```

The service restarts HotDog 5 s after it stops for any reason and deletes ROS logs older than
`LOG_DAYS` (7) at each start.

## Time

Every stamp comes from the robot computer's clock: `scripts/setup.sh install timesync`
(chrony) keeps it right and `health/status` warns when it drifts. The schedule runs on its
local time: set the time zone with `sudo timedatectl set-timezone Asia/Jakarta` (or the site's).

# Maintenance

## Schedule

| When        | Task                                                                                                                                                                                                                                  |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| every shift | `hotdog status`; ambient temperature; reports and alerts of the previous shift read                                                                                                                                                   |
| weekly      | clean the Airy windows, the pod's lenses and thermal window, the acoustic camera's front with a soft, dry cloth; check the payload rails' fasteners; dock contacts clean; copy the reports off the robot                              |
| monthly     | `scripts/setup.sh`; free disk (`hotdog status`: disk); a patrol watched end to end; the protective field test (section 4.3); stop point positions on the longest route                                                                |
| quarterly   | thermal check against a reference (a calibrated contact thermometer on a warm part, or a blackbody), within the pod maker's accuracy; acoustic camera against a known source; the M20's battery health and maintenance per its manual |
| yearly      | the Site Acceptance Test again; the limits reviewed with the substation owner                                                                                                                                                         |

Record every maintenance with its date and result.

## Update the software

```bash
cd ~/dev/HotDog
git pull
scripts/setup.sh install repos rosdep build
hotdog restart
scripts/setup.sh && hotdog status
```

Update with the robot on its dock and the schedule off; switch it on again after a patrol was
watched end to end. Read the CHANGELOG first: a new parameter may need a value in the site file.

## Back up and restore

| What                 | Where                              | Why                                             |
| -------------------- | ---------------------------------- | ----------------------------------------------- |
| the sites            | `~/.hotdog/sites/`                 | routes and inspection points: hours of teaching |
| the robot's settings | `/etc/hotdog/` (env, site, driver) | everything tuned on this robot                  |
| the reports          | `~/.hotdog/reports/`               | the inspection record                           |

```bash
sudo tar czf hotdog-backup-$(date +%Y%m%d).tgz /etc/hotdog ~/.hotdog/sites
```

Restore onto a new payload computer: install (docs/commissioning.md), unpack the archive,
`hotdog restart`. A site taught on one M20 works on another only if its dock is the same.

# Symptoms and fixes

| Symptom                                                      | Cause and fix                                                                                                                    |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| the bringup stops at start                                   | `hotdog logs`: an unknown section, a value out of range, a missing file named in the env file                                    |
| health WARN: a sensor below its rate                         | the LiDAR (`ros2 topic hz /lidar/front/points`), the M20 odometry (`/m20/odom`), the network cable                               |
| health ERROR: tf, odometry stale                             | the M20 driver lost the robot: `ping $ROBOT_IP`, the M20 switched on, `/m20/state`                                               |
| field BLIND or STALE, robot does not move                    | a LiDAR is down or its packets don't arrive: `require_all` stops the cloud; check both                                           |
| the robot stops for nothing                                  | dust or rain on the Airy windows; `filter.height_min` too low on uneven ground; the self filter too small after a payload change |
| it drifts off the route in turns                             | `speed.cruise` lower; the M20's speed calibration (driver README)                                                                |
| it stops short of the stop points far from the dock          | odometry drift: split the route, or tags                                                                                         |
| thermal values far from the reference                        | lens dirty or wet; emissivity of the target (the pod's settings); the target's region misses the part                            |
| `similar` findings on equipment with one hot phase by design | use `regions` covering comparable parts only, or `thermal: { enabled: true, strips: 0 }`                                         |
| acoustic: every target `noise`, known discharge missed       | the camera's band and threshold; `duration_sec` longer; distance and direction of the target                                     |
| acoustic: "gas leak mode"                                    | the camera's web page: partial discharge mode                                                                                    |
| alerts waiting, never sent                                   | `hotdog logs` (alert not sent: HTTP 401: wrong token; 400: wrong chat id; network: no route or proxy)                            |
| reports server unreachable                                   | the substation firewall (TCP 8088), `server.host`, another program on the port (`hotdog logs`)                                   |
| disk full                                                    | `retention.days` lower, `retention.min_free_gb`; ROS logs are pruned at each start                                               |

# Parameter reference

Every parameter of HotDog's own config files, with its default and what it does, read from the
files themselves. Dharma's parameters are in each `dharma_*` repository's README;
`ros2 param describe /<node> <name>` gives the unit, the range and whether it is live.

{{ parameter_reference }}
