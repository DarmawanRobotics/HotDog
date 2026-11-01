# Changelog

All notable changes to HotDog. Format: [Keep a Changelog](https://keepachangelog.com), versions follow [SemVer](https://semver.org).

## [Unreleased]

### Added

- `hotdog` from the Dharma template, on ROS 2 Foxy only.
- The Lynx M20 as the robot: `m20_bringup` started by `robot.launch.py`, its own odometry as
  the odometry (`camera_init -> body`), no mapping, the odometry start as the map origin.
- `hotdog_base`: both RoboSense Airy through `rslidar_sdk`, merged, self-filtered and leveled
  into `/lidar/points` for perception (360° sectors) and health.
- `hotdog_inspection` and `hotdog_interfaces`: inspection at every stop point (the follower's
  hook), points matched by position from `<site>/inspection.yaml`, overheat analysis with the
  UniPod MT11 (absolute, over ambient, between similar components), reports with thermal and
  visible images, `inspection/add_target` to teach targets from the pod's view.
- The bringup starts `unipod_driver` (`pod`, `pod_ip`) and `inspection_node` (`inspection`);
  `sites_dir` defaults to `~/.hotdog/sites` for every node.
- Partial discharge at acoustic targets with the Hertzinno HZ-FA-371 over its HTTP API (its
  driver is ROS 1): one detection measured after the robot stopped, corona / surface /
  floating judged by configurable severities and intensity, sound map and PRPD photos kept.
- `hotdog_patrol`: `patrol/start` from the dock (checks, `localization/assume_origin`, stand-up,
  AUTO, route, follower), the patrol followed to the end of its route, a summary of the
  inspections on the way, back to the dock with `charge_start`, patrols at fixed local times.
- Patrol watchdog: back to the dock below `abort.min_battery`, after `abort.max_duration_min`
  or blocked for `abort.hold_timeout_sec`; stopped when off the route, lost or the follower is
  silent; an operator pause, the e-stop or REMOTE is never overruled.
- The way back to the dock: the taught route reversed from the earliest waypoint near the robot,
  without stop points, to `abort.dock_clearance_m` before the dock, then `charge_start`;
  `patrol/return` on request, `PatrolStatus.RETURNING`, `returned` and `battery`.
- A patrol started without a route runs the route patrolled last on the site.
- The patrol summary lists the report directories of its inspection points.
- `PARAMS_FILE` in `/etc/hotdog/hotdog.env`: this robot's and site's parameters
  (`/etc/hotdog/site.yaml`) on top of `config/stack.yaml`, so a schedule survives a restart.
- Guides: [commissioning](docs/commissioning.md) of a new M20 or substation and
  [operations](docs/operations.md) for every shift.
