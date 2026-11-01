# hotdog_reports

The reports of HotDog on the robot, as pages any browser on the substation network opens:
one page per patrol with every point, every finding against the earlier rounds and the
evidence images, a page per day, a front page of every day, a disk that never fills up, and a
read-only web server.

```
http://<robot>:8088/                              every day, newest first
http://<robot>:8088/<YYYYMMDD>/                   the day: patrols, points, findings.csv
http://<robot>:8088/<YYYYMMDD>/patrol_<HHMMSS>.html   one patrol (prints to PDF from the browser)
```

## Node

`report_node` (`ros2 launch hotdog_reports reports.launch.py`, started by
`ros2 launch hotdog robot.launch.py`, `reports:=false` or `REPORTS=false` to leave it out):

| Interface           | Type                                 |                                                         |
| ------------------- | ------------------------------------ | ------------------------------------------------------- |
| `patrol/status`     | `hotdog_interfaces/PatrolStatus`     | a patrol that ended with its summary: render its page   |
| `inspection/report` | `hotdog_interfaces/InspectionReport` | a point inspected: refresh its day                      |
| `reports/rebuild`   | `std_srvs/Trigger`                   | render every page again (after changing `title`, etc.)  |
| HTTP `server.port`  | read-only files of `reports_dir`     | GET and HEAD only, nothing cached, `..` never leaves it |

At start the pages that are missing are rendered (a patrol that ended while the node was down
gets its page).

## A patrol page

| Part       |                                                                                                     |
| ---------- | --------------------------------------------------------------------------------------------------- |
| header     | site, route, start, state (`returned to the dock` when the watchdog brought it back)                |
| summary    | worst finding, points inspected, findings per severity, duration                                    |
| points     | time, point, state (done, partial, failed), severity, findings                                      |
| each point | position, every finding: check, region or discharge type, value, reference, Δ, **last round**, note |
| evidence   | thermal and visible image per target, sound map and PRPD for partial discharge                      |

**Last round** is the same finding (site, point, target, check, region or type) the last time
it was measured within `trend_days`: its value, the change (red when it rose) and how many
earlier rounds there are. A clamp that is still `normal` but 6 °C hotter than yesterday shows
up here before it crosses a limit.

The page prints on A4, one point per page; the images are linked from the point folders, so
copy the whole day folder to keep a report with its evidence.

## Retention

Every `retention.period_min`: days older than `retention.days` are deleted, then the oldest
days while less than `retention.min_free_gb` is free on the disk. Today is never deleted.
Copy what must be kept off the robot (see the operations guide).

## Parameters

[config/reports.yaml](config/reports.yaml); every one with its range:
`ros2 param describe /report_node <name>`. Name the robot and the site in the pages with
`robot_name` and `title` in the site file:

```yaml
report_node:
  ros__parameters:
    title: GI Cawang 150 kV
    robot_name: HotDog 01
```

The server listens on every interface by default (`server.host: 0.0.0.0`); on a network that
must not see the reports set `127.0.0.1` and open them through an SSH tunnel
(`ssh -L 8088:localhost:8088 robot@<ip>`).

## Test

```bash
colcon test --packages-select hotdog_reports && colcon test-result --verbose
```

`test/unit`: patrols and their points (old summaries too), the last round of each finding,
the patrol, day and front pages, escaping, the builder, retention by age and free space, the
server (files only, never outside the folder, no POST). `test/ros`: missing pages rendered at
start, a page when a patrol ends, the day refreshed by an inspection, `reports/rebuild`.
