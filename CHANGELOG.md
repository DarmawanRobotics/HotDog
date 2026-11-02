# Changelog

All notable changes to HotDog. Format: [Keep a Changelog](https://keepachangelog.com), versions follow [SemVer](https://semver.org).

## [Unreleased]

First complete version of HotDog: substation patrol and inspection on the Deep Robotics Lynx M20,
ROS 2 Foxy on Ubuntu 20.04, built on Dharma. CI builds the whole workspace on Foxy and runs
every test.

### Added

**Robot and stack**

- The bringup `hotdog` from the Dharma template: `robot.launch.py` starts `m20_bringup`, both
  Airy, the UniPod MT11, the Dharma stack and the HotDog nodes, each switchable (`pod`,
  `inspection`, `patrol`, `reports`, `alerts`); `sim.launch.py` runs the stack on dharma_sim.
- Odometry only: the M20's own odometry (`camera_init -> body`), no mapping, the dock as the map
  origin, re-anchored before every patrol; `sites_dir` defaults to `~/.hotdog/sites`.
- `hotdog_base`: both RoboSense Airy through `rslidar_sdk`, merged, self-filtered and leveled
  into `/lidar/points` for the 360° sectors, the protective field and health.
- Layered configuration: the robot profile (`ROBOT_PARAMS`), `config/stack.yaml`, this robot's
  and site's `/etc/hotdog/site.yaml` (`PARAMS_FILE`), the env file.

**Inspection**

- `hotdog_inspection` and `hotdog_interfaces`: inspection at every stop point (the follower's
  hook), points matched by position from `<site>/inspection.yaml`, targets taught from the pod's
  view (`inspection/add_target`).
- Overheat analysis with the UniPod MT11: absolute, over ambient and between similar components
  (NETA MTS defaults), thermal and visible evidence.
- Partial discharge with the Hertzinno HZ-FA-371 over its HTTP API: one detection after the
  robot stopped, corona / surface / floating by configurable severities and intensity, sound map
  and PRPD kept.

**Patrols**

- `hotdog_patrol`: `patrol/start` from the dock on demand or at fixed local times (checks,
  `localization/assume_origin`, stand-up, AUTO, route, follower), a summary with the report of
  every inspection point, back to the dock with `charge_start`; without a route, the route
  patrolled last on the site.
- The watchdog: back to the dock below `abort.min_battery`, after `abort.max_duration_min` or
  blocked for `abort.hold_timeout_sec`; stopped when off the route, lost or the follower is
  silent; an operator pause, the e-stop or REMOTE is never overruled.
- The way back: the taught route reversed from the nearest waypoint of its first pass, without
  stop points, to `abort.dock_clearance_m` before the dock; `patrol/return` on request,
  `PatrolStatus.RETURNING`, `returned` and `battery`.

**Results**

- `hotdog_reports`: a page per patrol with every finding against the last round and the
  evidence, day and front pages, retention by age and free space, served read-only on port 8088.
- `hotdog_alerts`: warning and critical findings with their image, failed, stopped, returned and
  finished patrols, health ERROR, to Telegram (English or Bahasa Indonesia) and a JSON webhook,
  spooled on disk while the uplink is down; `alerts/test` (`TELEGRAM_BOT_TOKEN`,
  `HOTDOG_WEBHOOK_TOKEN`).

**Operation**

- The `hotdog` command for operators (`scripts/hotdog.sh`): status, patrol, return, stop, pause,
  resume, estop, release, teach, aim, routes, site, anchor, dock, stand, sit, ambient, schedule,
  reports, alert-test, logs, restart; `ros2 run hotdog status` for the robot at a glance.
- `scripts/setup.sh` (tools, repos, rosdep, build, cli, service, timesync), a systemd service
  that restarts HotDog and prunes old ROS logs, `scripts/env.sh`, tmux layouts for the robot and
  the simulator, the Foxy dev container.

**Documentation**

- The User Manual, the Technician Guide with the parameter reference, and the Site Acceptance
  Test as A5 PDFs built from Markdown (CI warns when one is stale); commissioning and operations
  guides; a README in every package.
