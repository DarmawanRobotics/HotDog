"""
What a patrol report shows, read from the files the patrol and the inspections wrote.

    <reports_dir>/<YYYYMMDD>/patrol_<HHMMSS>.json          patrol_node's summary
    <reports_dir>/<YYYYMMDD>/<HHMMSS>_<point>/report.json  inspection_node, one per point
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import os
import re

from dharma_utils.io import read_json

SEVERITIES = ('normal', 'attention', 'warning', 'critical')
DAY_RE = re.compile(r'^\d{8}$')
POINT_DIR_RE = re.compile(r'^(\d{6})_(.+)$')
PATROL_RE = re.compile(r'^patrol_(\d{6})\.json$')


def rank(severity: str) -> int:
    """Return the order of a severity name (unknown: normal)."""
    return SEVERITIES.index(severity) if severity in SEVERITIES else 0


@dataclass
class Point:
    """One inspected point: its report.json and the folder it lives in."""

    directory: str
    data: dict

    @property
    def name(self) -> str:
        """Return the point's name."""
        return str(self.data.get('point', os.path.basename(self.directory)))

    @property
    def severity(self) -> str:
        """Return the point's highest severity."""
        return str(self.data.get('severity', 'normal'))

    @property
    def findings(self) -> list[tuple[dict, dict]]:
        """Return (target, finding) of every finding."""
        return [(t, f) for t in self.data.get('targets', []) for f in t.get('findings', [])]


@dataclass
class Patrol:
    """One patrol: its summary and its points in the order they were inspected."""

    path: str
    summary: dict
    points: list[Point] = field(default_factory=list)

    @property
    def started(self) -> datetime:
        """Return when the patrol started (local time)."""
        return datetime.fromtimestamp(float(self.summary.get('started') or 0.0))

    @property
    def html(self) -> str:
        """Return the path of the patrol's HTML report."""
        return os.path.splitext(self.path)[0] + '.html'


def load_point(directory: str) -> Point | None:
    """Return the point of a report folder, None without a readable report.json."""
    data, _error = read_json(os.path.join(directory, 'report.json'))
    return Point(directory, data) if isinstance(data, dict) else None


def load_patrol(path: str) -> Patrol | None:
    """Return the patrol of a summary file with its points, None when unreadable."""
    summary, _error = read_json(path)
    if not isinstance(summary, dict):
        return None
    patrol = Patrol(path, summary)
    directories = summary.get('inspections')
    if not isinstance(directories, list):
        directories = guess_points(os.path.dirname(path), patrol.started, summary)
    for directory in directories:
        point = load_point(str(directory))
        if point is not None:
            patrol.points.append(point)
    return patrol


def guess_points(day_dir: str, started: datetime, summary: dict) -> list[str]:
    """Return the point folders of the day inside the patrol's time (older summaries)."""
    end = started + timedelta(seconds=float(summary.get('duration_sec') or 0.0))
    first, last = started.strftime('%H%M%S'), end.strftime('%H%M%S')
    out = []
    for name in sorted(os.listdir(day_dir)) if os.path.isdir(day_dir) else []:
        match = POINT_DIR_RE.match(name)
        if match and first <= match.group(1) <= last:
            out.append(os.path.join(day_dir, name))
    return out


def day_dirs(root: str) -> list[str]:
    """Return the day folder names (YYYYMMDD) under root, oldest first."""
    if not os.path.isdir(root):
        return []
    names = (n for n in os.listdir(root) if DAY_RE.match(n))
    return sorted(n for n in names if os.path.isdir(os.path.join(root, n)))


def patrol_files(day_dir: str) -> list[str]:
    """Return the patrol summaries of a day, in time order."""
    if not os.path.isdir(day_dir):
        return []
    return [os.path.join(day_dir, n) for n in sorted(os.listdir(day_dir)) if PATROL_RE.match(n)]


def point_dirs(day_dir: str) -> list[str]:
    """Return the point report folders of a day, in time order."""
    if not os.path.isdir(day_dir):
        return []
    names = sorted(n for n in os.listdir(day_dir) if POINT_DIR_RE.match(n))
    return [os.path.join(day_dir, n) for n in names if os.path.isdir(os.path.join(day_dir, n))]
