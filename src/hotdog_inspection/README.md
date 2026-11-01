# hotdog_inspection

Substation inspection at the stop points of a patrol: the UniPod MT11 is pointed at each piece
of equipment taught there and its temperatures are judged for overheating, the Hertzinno
HZ-FA-371 listens for partial discharge, and a report with the thermal, visible and sound map
images is kept on the robot and published.

## Node

`inspection_node` (`ros2 launch hotdog_inspection inspection.launch.py`, started by
`ros2 launch hotdog robot.launch.py`):

| Interface               | Type                                 |                                                                                                                                      |
| ----------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| `inspection/inspect`    | `std_srvs/Trigger`                   | inspect the point where the robot stands (the follower's hook)                                                                       |
| `inspection/add_target` | `hotdog_interfaces/AddTarget`        | teach a target from the pod's current pan, tilt and zoom                                                                             |
| `inspection/report`     | `hotdog_interfaces/InspectionReport` | everything measured at one point, its highest severity                                                                               |
| `inspection/status`     | `hotdog_interfaces/InspectionStatus` | latched: idle / inspecting / disabled, points, targets, pod, ambient                                                                 |
| `site/status`           | `dharma_interfaces/SiteStatus`       | the active site (input)                                                                                                              |
| `navigation/stop_point` | `dharma_interfaces/StopPointEvent`   | where the robot stopped (input)                                                                                                      |
| `/unipod/*`             | `unipod_msgs`                        | `set_angle`, `set_zoom`, `get_temperature`, `thermal_control`, `recenter`, `status`, `attitude`, both image streams while inspecting |
| HZ-FA-371               | HTTP (`acoustic.host`)               | login, detection settings, start / stop, records and their photos                                                                    |

The path follower calls `inspection/inspect` at every stop point
(`hooks.inspection: [/inspection/inspect]` in the bringup's `stack.yaml`) and waits for the
answer up to `dwell + hooks.inspection_timeout_sec`. A stop with no inspection point within
`match_radius_m` answers at once; a missing or failing pod is reported, never raised, and the
patrol goes on.

## Inspection points

`<sites_dir>/<site>/inspection.yaml`, next to the site's taught routes. A point is where the
robot stands, in the map frame (the dock is the origin, see the bringup's "Odometry only"), so
every route stopping near it inspects it:

```yaml
points:
  - name: bay1_disconnector
    x: 12.40
    y: -3.10
    targets:
      - name: bay1_ds_clamps
        pan_deg: 35.0 # pod yaw, positive right
        tilt_deg: -10.0 # pod pitch, positive up (-90 .. 30)
        zoom: 4.0
        thermal: { enabled: true, strips: 3, max_temp_c: 0.0 }
      - name: bay1_ct_terminals
        pan_deg: -20.0
        tilt_deg: 5.0
        zoom: 2.0
        thermal:
          regions: # boxes in thermal pixels (640 x 512), compared with each other
            - { name: r, box: [80, 120, 200, 260] }
            - { name: s, box: [260, 120, 380, 260] }
            - { name: t, box: [440, 120, 560, 260] }
        acoustic: { enabled: true, duration_sec: 5.0 } # partial discharge, 5 s detection
```

**Teach** at the stop while the route is taught (the robot stands where it will stop) or while
the patrol dwells there: aim the pod (`/unipod/ptz_cmd`, `/unipod/set_angle`, `set_zoom`), then

```bash
ros2 service call /inspection/add_target hotdog_interfaces/srv/AddTarget \
  "{name: bay1_ds_clamps, thermal: true, acoustic: true, strips: 3}"
```

The target goes to the point within `match_radius_m` (or a new point named after it, or the
`point` you name). Edit the file for regions or limits; it is read at every inspection.

## Overheat analysis

Per target, the pod measures each region (`samples` times, the median kept): explicit
`regions`, or `strips` side-by-side strips of the frame (three phases), or the whole frame.
The hottest region is judged by three criteria, each with attention / warning / critical
thresholds (degC), after the usual infrared-inspection practice (NETA MTS):

| Criterion  | Value                                                                  | Default thresholds                                       |
| ---------- | ---------------------------------------------------------------------- | -------------------------------------------------------- |
| `absolute` | the hottest temperature                                                | 80 / 90 / 105 (or the target's `max_temp_c` as critical) |
| `ambient`  | the hottest temperature over `thermal.ambient_c`                       | 11 / 21 / 41                                             |
| `similar`  | the hottest region over the median of the others (two regions or more) | 2 / 4 / 16                                               |

`thermal.ambient_c` is live: set it to the air temperature of the day
(`ros2 param set /inspection_node thermal.ambient_c 33.0`). A flat-field correction (shutter
refresh) runs once per point before measuring. The MT11 gives temperatures per point, box or
frame, not a radiometric image: the evidence images are the camera streams.

## Partial discharge

The HZ-FA-371's ROS driver ([hertzino_driver](https://github.com/DarmawanRobotics/hertzino_driver))
is ROS 1 Noetic; HotDog runs Foxy, so `inspection_node` talks to the camera's HTTP API itself
(`core/hertzino.py`, manual V5.1). For each acoustic target, after the robot stopped:

1. the camera must be in partial discharge mode (gas leak mode is refused), the detection time
   is set (`duration_sec` of the target, else `acoustic.duration_sec`);
2. a detection already running (continuous monitoring) is stopped, the newest record noted;
3. a detection starts; the result is the record that appears a whole detection time later (a
   record of a detection that started before the robot stood still is never taken);
4. the detection is stopped, the sound map and PRPD photos are saved next to the report.

| Type       | Default severity |                                                       |
| ---------- | ---------------- | ----------------------------------------------------- |
| `noise`    | normal           | no discharge                                          |
| `corona`   | attention        | common on outdoor high-voltage parts: watch the trend |
| `surface`  | warning          | tracking on insulators, terminations                  |
| `floating` | critical         | a floating (loose) part                               |

`acoustic.intensity_warning` / `intensity_critical` raise the severity by the sound map
intensity once the site's levels are known (0: off). The camera's password comes from
`$HERTZINO_PASSWORD` (`/etc/hotdog/hotdog.env`), never from a parameter; the factory one is used
with a warning when it is unset. Give the robot computer an address in the camera's subnet
(factory `192.168.2.204`, e.g. `192.168.2.10/24`); `inspection/status` shows
`acoustic_connected`.

## Reports

```
<reports_dir>/<YYYYMMDD>/<HHMMSS>_<point>/report.json, <target>_thermal.jpg, <target>_visible.jpg,
                                          <target>_soundmap.jpg, <target>_prpd.jpg
<reports_dir>/<YYYYMMDD>/findings.csv           every finding of the day, one row each
```

`report.json` holds the point, the robot's position, the state (`done`, `partial`, `failed`),
the highest severity and every finding with its value, reference and delta.
`inspection/report` carries the same, with the image paths.

## Parameters

[config/inspection.yaml](config/inspection.yaml); every one with its range:
`ros2 param describe /inspection_node <name>`. `sites_dir` and `reports_dir` default to
`~/.hotdog/sites` and `~/.hotdog/reports` (the bringup passes its `sites_dir`).

## Test

```bash
colcon test --packages-select hotdog_inspection && colcon test-result --verbose
```

`test/unit`: the criteria, the plan file, the point sequence against a fake pod (order,
samples, deadline, failures), the reports, the camera client and a detection against a
stand-in HZ-FA-371 (login, 401, an old record never taken, photos, gas leak mode). `test/ros`: the node against a fake
`unipod_driver` (inspect a taught point with a hot phase, teach a target).
