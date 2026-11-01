# hotdog_patrol

Route patrols of HotDog: from the dock, on demand or at fixed times of the day, along a taught
route whose stop points are inspected, with a summary of what the inspections found, and back
to the dock.

## Node

`patrol_node` (`ros2 launch hotdog_patrol patrol.launch.py`, started by
`ros2 launch hotdog robot.launch.py`):

| Interface                                                        | Type                                 |                                                        |
| ---------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------ |
| `patrol/start`                                                   | `hotdog_interfaces/StartPatrol`      | start a patrol on a route of the active site           |
| `patrol/stop`                                                    | `std_srvs/Trigger`                   | stop it (the follower stops, the robot stands)         |
| `patrol/status`                                                  | `hotdog_interfaces/PatrolStatus`     | latched: state, route, findings per severity, schedule |
| `navigation/status`                                              | `dharma_interfaces/NavigationStatus` | the follower, to the end of the route (input)          |
| `inspection/report`                                              | `hotdog_interfaces/InspectionReport` | the points inspected on the way (input)                |
| `health/status`, `control/status`, `/m20/battery`, `site/status` |                                      | the start checks (input)                               |

## A patrol

```bash
ros2 service call /patrol/start hotdog_interfaces/srv/StartPatrol "{route: 20261101_093000}"
ros2 topic echo /patrol/status
ros2 service call /patrol/stop std_srvs/srv/Trigger
```

`route` is a file of the active site's `routes/` (the `.csv` is optional); empty: the route
loaded last. The start sequence runs in order and stops at the first step that fails
(`patrol/status` says which and why):

| Step      |                                                                                               |
| --------- | --------------------------------------------------------------------------------------------- |
| checks    | health level at most `start.max_health` (WARN), no e-stop, battery ≥ `start.min_battery`      |
| re-anchor | `localization/assume_origin`: the robot stands at the dock, the map origin (`start.reanchor`) |
| stand up  | `/m20/stand_up` (`start.stand_up_service`, empty: skipped)                                    |
| auto      | `control/set_mode` auto: navigation drives through the control mux                            |
| route     | `navigation/load_path` `<site>/routes/<route>.csv`                                            |
| start     | `navigation/start`                                                                            |

Then the follower patrols; at each stop point it calls `inspection/inspect`. The patrol ends
when the follower reaches the end of the route (`done`), fails (`failed`) or is stopped
(`stopped`). The summary goes to `<reports_dir>/<day>/patrol_<time>.json` (route, duration,
points inspected, findings per severity, the worst one) next to the day's inspection reports,
and after a `done` patrol the M20 is sent back to its dock (`/m20/charge_start`,
`finish.dock_service`).

**Odometry only.** The re-anchoring makes the dock the origin of every patrol: start each patrol
from the dock, where the route was taught from. A route ending at the dock's approach lets the
M20 dock by itself afterwards.

## Schedule

```bash
ros2 param set /patrol_node schedule.enabled true
ros2 param set /patrol_node schedule.times "['06:00', '14:00', '22:00']"
ros2 param set /patrol_node schedule.route 20261101_093000
```

At each time (local time of the robot computer) a patrol starts, unless one is running; a
time missed by more than `schedule.window_min` (robot busy, off) is skipped, not caught up.
Keep the schedule in the robot's site file (`params_file`) to have it after a restart.

## Parameters

[config/patrol.yaml](config/patrol.yaml); every one with its range:
`ros2 param describe /patrol_node <name>`. `{robot_ns}` in a topic or service name is the
driver namespace (`robot_ns`, passed by the bringup).

## Test

```bash
colcon test --packages-select hotdog_patrol && colcon test-result --verbose
```

`test/unit`: the start steps, the patrol's end from the follower's states (a state left from
the last patrol is ignored), the findings, route names, the schedule. `test/ros`: the node
against a fake stack (a patrol from the dock to the end of the route with its summary and the
dock, a refused stand-up, one patrol at a time).
