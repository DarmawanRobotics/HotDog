# Contributing

The full conventions are in
[CONTRIBUTING.md](https://github.com/DarmawanRobotics/Dharma/blob/main/CONTRIBUTING.md) of the hub
and the manual's development chapter. In short:

## Code

- `<pkg>/core/` is pure Python + numpy (no rclpy, messages, tf2 or launch); `utils/` holds the
  ROS-side helpers; nodes are thin and subclass `dharma_utils.ros.DharmaNode`.
- Modules at most 300 lines (tests 400); ruff's complexity limits are on: split, do not `noqa`.
- Families of algorithms: an abstract base in `base.py`, one implementation per file, a
  `dharma_utils.plugins.Registry` open to entry points.
- Nothing robot-specific in code: geometry, limits and frames come from the `robot.*` profile.
- Parameters are dataclasses with `param(default, doc=, unit=, min=, max=)`; safety values
  `live=False`; units in names (`_sec`, `_m`, `_deg`), radians inside.
- ROS 2 Foxy, Humble and Jazzy, Python 3.8+ (`from __future__ import annotations` first in every
  module, no 3.9+ runtime features), numpy >= 1.17; distro differences only through
  `dharma_utils.ros` (`compat`, `launch`), never a branch on the distro in a package.
- English, one-line docstrings, type hints, frozen dataclasses, `Enum` states.

## Lint, build, test

```bash
pip install pre-commit && pre-commit install
pre-commit run --all-files            # ruff, clang-format, prettier, shellcheck, yaml/xml checks
colcon build && colcon test && colcon test-result --verbose
PYTHONPATH=$PWD python -m pytest -q test/unit    # fast, from a package directory, no ROS
```

- `test/unit`: pytest on `core/`. `test/ros`: rclpy in-process node tests (unique node names,
  `rclpy.init()` / `try_shutdown()` per test). `test/test_style.py`: the package conventions.
- Every fixed defect gets a regression test.
- `ament_python` packages declare `extras_require={'test': ['pytest']}`, otherwise colcon runs no
  tests: check that `colcon test-result` reports your tests, not 0.
- Never name a module-level test helper `setup` or `teardown`: the Foxy, Humble and Jazzy pytest
  run them as nose-style fixtures. Foxy's CI runs pytest 4.6.

## Commits and pull requests

- Conventional Commits, one short line: `fix(mux): rotation inside the field`.
- One topic per pull request into `main`; CI must be green on Foxy, Humble and Jazzy.
- A change across several repositories uses the **same branch name** in each: CI builds the
  dependencies from that branch when it exists.
- Safety-relevant changes (speeds, limits, e-stop, avoidance, the mux, the robot profile) need a
  test that drives the logic, a note on how it was tried on the robot and a CHANGELOG entry.

## Releases

SemVer with a Keep a Changelog `CHANGELOG.md` in every repository; the stack moves together
(0.1 -> 0.2 was a breaking release of every package). Products pin the release tags.

## Documentation

`docs/` of the hub: `make -C docs` builds the diagrams, the manual and the paper (draw.io and a
LaTeX installation with latexmk); `make -C docs reference SRC=<dir with the dharma_* checkouts>`
regenerates the manual's parameter and interface tables from the code; `make -C docs pdf` rebuilds
the committed PDFs in `docs/pdf/`. This guide is plain Markdown in `docs/guide/`.
