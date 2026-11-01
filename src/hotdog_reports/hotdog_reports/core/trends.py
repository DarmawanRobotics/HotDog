"""
Earlier findings of the same target: what each finding is compared with in a report.

Read from the daily findings tables (<day>/findings.csv) that inspection_node appends to. A
finding is identified by site, point, target, criterion and label (the region or the discharge
type), so the hottest phase of a clamp is compared with the hottest phase of the last round.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import os

from hotdog_reports.core.model import day_dirs

Key = tuple  # (site, point, target, criterion, label)


@dataclass(frozen=True)
class Earlier:
    """The last earlier value of a finding and how many rounds measured it."""

    time: str
    value: float
    severity: str
    rounds: int
    peak: float


def key_of(site: str, point: str, target: str, finding: dict) -> Key:
    """Return the identity of a finding."""
    return (site, point, target, finding.get('criterion', ''), finding.get('label', ''))


def history(root: str, before: datetime, days: int) -> dict:
    """Return {key: [(time, value, severity), ...]} of the findings before a time, oldest first."""
    if days <= 0:
        return {}
    first = (before - timedelta(days=days)).strftime('%Y%m%d')
    last = before.strftime('%Y%m%d')
    limit = before.isoformat(timespec='seconds')
    out: dict = {}
    for day in day_dirs(root):
        if not first <= day <= last:
            continue
        for row in read_rows(os.path.join(root, day, 'findings.csv')):
            if row.get('time', '') >= limit:
                continue
            try:
                value = float(row.get('value', 'nan'))
            except ValueError:
                continue
            key = (row.get('site', ''), row.get('point', ''), row.get('target', ''),
                   row.get('criterion', ''), row.get('label', ''))  # fmt: skip
            out.setdefault(key, []).append((row.get('time', ''), value, row.get('severity', '')))
    for rows in out.values():
        rows.sort()
    return out


def earlier(hist: dict, key: Key) -> Earlier | None:
    """Return the last earlier value of a finding, None when it is new."""
    rows = hist.get(key)
    if not rows:
        return None
    time, value, severity = rows[-1]
    return Earlier(time, value, severity, len(rows), max(v for _, v, _ in rows))


def read_rows(path: str) -> list[dict]:
    """Return the rows of a findings table ([] when missing or unreadable)."""
    try:
        with open(path, encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []
