#!/usr/bin/env python3
"""
Turn the Dharma template into a robot product repository (run once, after "Use this template").

    scripts/init_project.py --name MyRobot --package my_robot_bringup --robot-ns my_robot
    scripts/init_project.py --name MyRobot --package my_robot_bringup --dry-run

Renames the robot_bringup placeholder package everywhere, sets the robot namespace and the
container names, removes what only the Dharma hub needs (tooling/, the tooling sync, this
script, the manual, the paper, the diagram sources, the PDFs and the guide unless
--keep-docs), resets the version to 0.1.0 and rewrites README.md and CHANGELOG.md. Commit the
result.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import sys

PLACEHOLDER = 'robot_bringup'
PLACEHOLDER_RE = re.compile(r'(?<![A-Za-z0-9])robot_bringup(?![A-Za-z0-9])')
NAME_RE = re.compile(r'^[A-Z][A-Za-z0-9]*$')
PACKAGE_RE = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$')
NAMESPACE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
SKIP_DIRS = {'.git', 'build', 'install', 'log', '__pycache__', '.pytest_cache', '.ruff_cache'}
SKIP_PATHS = ('src/dharma', 'src/external')  # stack checkouts (vcs import)
HUB_ONLY = ('tooling', 'scripts/sync_tooling.sh', 'scripts/init_project.py', 'scripts/test')
DOCS_ONLY = (
    'docs/manual',
    'docs/paper',
    'docs/diagrams',
    'docs/guide',
    'docs/pdf',
    'docs/Makefile',
    'docs/authors.tex',
    'docs/macros.tex',
)
VERSION = '0.1.0'


class InitError(ValueError):
    """The arguments or the repository do not allow the conversion."""


@dataclass(frozen=True)
class Options:
    """What the product is called."""

    name: str
    package: str
    robot_ns: str
    owner: str = 'DarmawanRobotics'
    keep_docs: bool = False

    @property
    def slug(self) -> str:
        """Return the lower-case project name for containers, e.g. MyRobot -> my_robot."""
        return snake(self.name)


def snake(name: str) -> str:
    """Return CamelCase as snake_case: MyRobot -> my_robot, HTTPRobot -> http_robot."""
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text).lower()


def validate(o: Options) -> list[str]:
    """Return every problem with the options."""
    problems = []
    if not NAME_RE.match(o.name):
        problems.append(f'--name {o.name!r}: CamelCase repository name, e.g. MyRobot')
    if not PACKAGE_RE.match(o.package):
        problems.append(f'--package {o.package!r}: snake_case package name, e.g. my_robot_bringup')
    elif o.package.startswith('dharma_') or o.package == PLACEHOLDER:
        problems.append(f'--package {o.package!r}: dharma_* and {PLACEHOLDER} are taken')
    if not NAMESPACE_RE.match(o.robot_ns):
        problems.append(f'--robot-ns {o.robot_ns!r}: one ROS namespace segment, e.g. my_robot')
    return problems


def replace_package(text: str, package: str) -> str:
    """Replace the placeholder package name (also inside longer names like robot_bringup_x)."""
    return PLACEHOLDER_RE.sub(package, text)


def rename_path(rel: str, package: str) -> str:
    """Return the path with every placeholder component renamed."""
    return '/'.join(package if part == PLACEHOLDER else part for part in rel.split('/'))


def removed(rel: str, o: Options) -> bool:
    """Return True for hub-only files (and the Dharma documentation sources)."""
    prefixes = HUB_ONLY + (() if o.keep_docs else DOCS_ONLY)
    return any(rel == p or rel.startswith(p + '/') for p in prefixes)


# (path, pattern, replacement) edits applied after the package rename; {ns} {slug} {name}
PKG = f'src/{PLACEHOLDER}'
EDITS = (
    (f'{PKG}/{PLACEHOLDER}/bringup.py', r"NS = '[^']*'", "NS = '{ns}'"),
    ('scripts/tmux/robot.yaml', r'(?m)^  ROBOT_NS: .*$', '  ROBOT_NS: {ns}'),
    ('scripts/tmux/sim.yaml', r'(?m)^  ROBOT_NS: .*$', '  ROBOT_NS: {ns}'),
    ('scripts/setup.sh', r"'ROBOT_NS=[^']*'", "'ROBOT_NS={ns}'"),
    ('compose.yaml', r'(?m)^name: .*$', 'name: {slug}'),
    ('compose.yaml', r'dharma-dev', '{slug}-dev'),
    ('compose.yaml', r'hostname: dharma-', 'hostname: {slug}-'),
    ('.devcontainer/devcontainer.json', r'"name": "dharma', '"name": "{slug}'),
    (f'{PKG}/package.xml', r'<version>[^<]*</version>', f'<version>{VERSION}</version>'),
    (f'{PKG}/setup.py', r"version='[^']*'", f"version='{VERSION}'"),
)  # fmt: skip


def edit(rel: str, text: str, o: Options) -> str:
    """Return the text of a file (by its template path) as the product needs it."""
    text = replace_package(text, o.package)
    values = {'ns': o.robot_ns, 'slug': o.slug, 'name': o.name}
    for path, pattern, replacement in EDITS:
        if path == rel:
            text = re.sub(pattern, replacement.format(**values), text)
    if rel == 'README.md':
        text = readme(o)
    elif rel == 'CHANGELOG.md':
        text = changelog(o)
    elif rel == 'docs/README.md' and not o.keep_docs:
        text = f'# {o.name} documentation\n\nProduct documentation goes here.\n'
    return text


def readme(o: Options) -> str:
    """Return the README of the new product."""
    repo = f'https://github.com/{o.owner}/{o.name}'
    return f"""<div align="center">

# {o.name}

**A robot product on the Dharma autonomy stack.**

[![CI]({repo}/actions/workflows/ci.yml/badge.svg?branch=main)]({repo}/actions/workflows/ci.yml)
[![ROS 2](https://img.shields.io/badge/ROS%202-Foxy%20%7C%20Humble%20%7C%20Jazzy-22314E?logo=ros&logoColor=white)](https://docs.ros.org/)
[![Dharma](https://img.shields.io/badge/stack-Dharma-4A78C2)](dharma.repos)

</div>

---

`{o.package}` brings the robot up: its profile (`config/robot.yaml`), the per-node overrides of
the stack (`config/stack.yaml`) and one launch for everything. The Dharma packages come from
[dharma.repos](dharma.repos), the sensor driver and FAST-LIO from [external.repos](external.repos).

## Quick start

```bash
scripts/dev.sh up                     # dev container (--distro foxy|humble|jazzy)
scripts/dev.sh build && scripts/dev.sh test
scripts/dev.sh shell
ros2 launch {o.package} sim.launch.py rviz:=true                  # no robot needed
ros2 launch {o.package} robot.launch.py robot_driver:=<driver_pkg>  # on the robot
```

On the robot: `scripts/setup.sh install`, then `scripts/setup.sh install service`.
The robot driver runs in the namespace `/{o.robot_ns}` (`/{o.robot_ns}/cmd_vel`, `/{o.robot_ns}/odom`).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the conventions.
"""  # noqa: E501


def changelog(o: Options) -> str:
    """Return a fresh CHANGELOG."""
    return (
        f'# Changelog\n\nAll notable changes to {o.name}. Format: '
        '[Keep a Changelog](https://keepachangelog.com), versions follow '
        '[SemVer](https://semver.org).\n\n## [Unreleased]\n\n### Added\n\n'
        f'- `{o.package}` from the Dharma template.\n'
    )


def files(root: Path) -> list[str]:
    """Return the repository files (relative, '/' separated), stack checkouts excluded."""
    out = []
    for directory, dirs, names in os.walk(root):
        rel_dir = Path(directory).relative_to(root).as_posix()
        dirs[:] = sorted(
            d
            for d in dirs
            if d not in SKIP_DIRS and (f'{rel_dir}/{d}'.lstrip('./')) not in SKIP_PATHS
        )
        out += [Path(directory, n).relative_to(root).as_posix() for n in sorted(names)]
    return out


def plan(root: Path, o: Options) -> tuple[list, list]:
    """Return (removals, [(old, new, text or None)]) without touching anything."""
    if not (root / 'src' / PLACEHOLDER).is_dir():
        raise InitError(f'{root}: no src/{PLACEHOLDER} (already initialised?)')
    removals, changes = [], []
    for rel in files(root):
        if removed(rel, o):
            removals.append(rel)
            continue
        try:
            old = (root / rel).read_text(encoding='utf-8')
        except UnicodeDecodeError:
            old = None
        text = None if old is None else edit(rel, old, o)
        new = rename_path(rel, o.package)
        if new != rel or (text is not None and text != old):
            changes.append((rel, new, None if text == old else text))
    return removals, changes


def apply(root: Path, removals: list, changes: list) -> None:
    """Remove, move and rewrite the planned files, then drop emptied directories."""
    for rel in removals:
        (root / rel).unlink()
    for old, new, text in changes:
        if new != old:
            (root / new).parent.mkdir(parents=True, exist_ok=True)
            os.replace(root / old, root / new)
        if text is not None:
            (root / new).write_text(text, encoding='utf-8')
    for directory, _, _ in sorted(os.walk(root), key=lambda d: -len(d[0])):
        path = Path(directory)
        if path != root and '.git' not in path.parts and not any(path.iterdir()):
            path.rmdir()
    stale = root / 'src' / PLACEHOLDER
    if stale.exists():
        shutil.rmtree(stale)


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments and convert the repository."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('--name', required=True, help='CamelCase repository name (MyRobot)')
    parser.add_argument('--package', required=True, help='snake_case bringup package')
    parser.add_argument('--robot-ns', help='robot driver namespace (default: the name, snake)')
    parser.add_argument('--owner', default='DarmawanRobotics', help='GitHub owner for links')
    parser.add_argument('--keep-docs', action='store_true', help='keep the Dharma docs')
    parser.add_argument('--dry-run', action='store_true', help='print the changes only')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    o = Options(args.name, args.package, args.robot_ns or snake(args.name), args.owner,
                args.keep_docs)  # fmt: skip
    problems = validate(o)
    if problems:
        parser.error('; '.join(problems))
    root = Path(args.root)
    try:
        removals, changes = plan(root, o)
    except InitError as error:
        parser.error(str(error))
    for rel in removals:
        print(f'remove  {rel}')
    for old, new, text in changes:
        if old == new:
            print(f'edit    {old}')
        else:
            print(f'rename  {old} -> {new}' + (' (edited)' if text else ''))
    if not args.dry_run:
        apply(root, removals, changes)
        print(f'{o.name}: done; `pre-commit run --all-files` (re-pads tables), review, commit')
    return 0


if __name__ == '__main__':
    sys.exit(main())
