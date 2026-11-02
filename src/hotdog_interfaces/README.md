# hotdog_interfaces

The messages and services of HotDog's inspection and patrols.

| Interface          | Type    |                                                                                                 |
| ------------------ | ------- | ----------------------------------------------------------------------------------------------- |
| `Finding`          | message | one result: thermal criterion (absolute, ambient, similar) or acoustic detection                |
| `InspectionReport` | message | everything measured at one inspection point, with its highest severity                          |
| `InspectionStatus` | message | idle or inspecting, the site's points and targets, the sensors, the last severity               |
| `AddTarget`        | service | teach a target: the pod's pan, tilt and zoom where the robot stands                             |
| `PatrolStatus`     | message | the patrol running or the last one: state (incl. RETURNING), route, findings, battery, schedule |
| `StartPatrol`      | service | start a patrol from the dock on a route of the active site                                      |

Severities (`Finding.NORMAL`, `ATTENTION`, `WARNING`, `CRITICAL`) follow the usual
infrared-inspection practice (NETA MTS, ANSI table 100.18): possible, probable and major
deficiency. The thresholds are parameters of `inspection_node`.
