# Contributing

The conventions of every Dharma repository (the stack packages and the products made from this
template). The design behind them is in the [manual](docs/README.md).

## Code

| Rule          |                                                                                                                                                                                                                                    |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Layout        | `<pkg>/core/` pure Python + numpy (no rclpy, messages, tf2, launch), `<pkg>/utils/` ROS-side helpers, thin `*_node.py` nodes; `config/<pkg>.yaml`, `launch/<pkg>.launch.py`, `test/unit`, `test/ros`, `test/test_style.py`         |
| Size          | modules <= 300 lines, tests <= 400; ruff's complexity limits (12) are on: split, do not `noqa`                                                                                                                                     |
| Families      | an abstract base in `base.py`, one implementation per file, a `dharma_utils.plugins.Registry` (open to entry points, so a product adds one without forking)                                                                        |
| Nodes         | subclass `dharma_utils.ros.DharmaNode`, start with `run(MyNode)`; `declare_config` / `declare_robot`, `self.log`, `self.tf`, `every()`                                                                                             |
| Robot         | nothing robot-specific in code: geometry, limits and frames come from the `robot.*` profile (`dharma_utils.robot.RobotProfile`)                                                                                                    |
| Parameters    | dataclasses with `param(default, doc=, unit=, min=, max=)`, validated on start and on every `ros2 param set`; safety limits `live=False`; units in names (`_sec`, `_m`), radians inside                                            |
| Style         | English, one-line docstrings on public API, type hints, frozen dataclasses, `Enum` states, no `print`, no bare `except`, no commented-out code                                                                                     |
| Compatibility | ROS 2 Foxy, Humble and Jazzy, Python 3.8+ (`from __future__ import annotations`, no 3.9+ runtime features), numpy >= 1.17; distro differences only through `dharma_utils.ros`                                                      |
| Interfaces    | relative topic names, typed latched status messages, separate `Trigger` services for safety actions (never a SetBool "true = on")                                                                                                  |
| Launch        | `params_file`, `robot_params`, `use_sim_time`, `log_level`; parameters `[defaults, robot_params?, params_file?, {non-empty overrides}]`; no launch file includes another package's launch file (the product bringup composes them) |
| Tests         | every fixed defect gets a regression test; ROS tests use unique node names and `rclpy.init()` / `try_shutdown()` per test; never name a module-level helper `setup` / `teardown`                                                   |

Lint and format run through pre-commit, locally and in CI:

```bash
pip install pre-commit && pre-commit install
pre-commit run --all-files          # ruff, clang-format, prettier, shellcheck, yaml/xml checks
```

## Build and test

```bash
scripts/dev.sh up && scripts/dev.sh build && scripts/dev.sh test   # dev container, humble
scripts/dev.sh --distro jazzy up                                   # the same on jazzy (or foxy)
colcon build && colcon test && colcon test-result --verbose         # natively
```

`ament_python` packages declare `extras_require={'test': ['pytest']}`, otherwise colcon runs no
tests; check that `colcon test-result` reports your tests, not 0.

## Commits, branches and pull requests

- [Conventional Commits](https://www.conventionalcommits.org), one short line:
  `fix(mux): rotation inside the field`, `refactor(follower): split the state machine`,
  `feat(bringup)!: ...` for a breaking change.
- Branches `fix/<topic>`, `feat/<topic>`, `refactor/<topic>`, `docs/<topic>`, `ci/<topic>`; one
  topic per pull request into `main`. CI must be green on Foxy, Humble and Jazzy.
- A change across several repositories uses the **same branch name** in each: CI builds the
  dependencies from that branch when it exists, so the pieces are tested together.
- Safety-relevant changes (speeds, limits, e-stop, avoidance, the control mux, the robot
  profile) need a test that drives the logic, a note on how it was tried on the robot (slow,
  open area, someone at the e-stop) and a CHANGELOG entry.

## Releases

Every repository follows [SemVer](https://semver.org) with a [Keep a
Changelog](https://keepachangelog.com) `CHANGELOG.md`. A release bumps `package.xml` (and
`setup.py`), moves `[Unreleased]` to `## [x.y.z] - date` and is tagged `vx.y.z` on `main`. The
stack moves together: products pin the released tags in their `dharma.repos`.

## Maintainers: tooling

`tooling/` holds the canonical lint configuration and the per-repository CI (`ci-package.yml`).
After changing it, `scripts/sync_tooling.sh` copies it into every `dharma_*` checkout under
`src/` (`--check` lists what differs); commit the result in each repository.
