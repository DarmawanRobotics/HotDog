"""
Keeping the robot's disk from filling.

Days older than the retention are deleted, then the oldest days while too little space is
free. Today is never deleted.
"""

from __future__ import annotations

import contextlib
from datetime import date, timedelta
import os
import shutil

from hotdog_reports.core.model import day_dirs

GB = 1024**3


def expired(days: list[str], today: date, keep_days: int) -> list[str]:
    """Return the day folders older than keep_days (0: none)."""
    if keep_days <= 0:
        return []
    limit = (today - timedelta(days=keep_days)).strftime('%Y%m%d')
    return [d for d in days if d < limit]


def to_free(days: list[str], today: date, free: float, need: float, size) -> list[str]:
    """Return the oldest days whose deletion brings the free space to need (bytes).

    size(day) -> bytes is asked only for the days that go.
    """
    out, today_name = [], today.strftime('%Y%m%d')
    for day in sorted(days):
        if free >= need or day >= today_name:
            break
        out.append(day)
        free += size(day)
    return out


def tree_size(path: str) -> int:
    """Return the bytes of the files under path."""
    total = 0
    for directory, _dirs, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):
                total += os.path.getsize(os.path.join(directory, name))
    return total


def prune(root: str, today: date, keep_days: int, min_free_gb: float) -> list[str]:
    """Delete expired days, then the oldest while less than min_free_gb is free; return them."""
    days = day_dirs(root)
    gone = expired(days, today, keep_days)
    left = [d for d in days if d not in gone]
    for day in gone:
        shutil.rmtree(os.path.join(root, day), ignore_errors=True)
    if min_free_gb > 0.0 and os.path.isdir(root):
        free = float(shutil.disk_usage(root).free)
        more = to_free(
            left, today, free, min_free_gb * GB, lambda d: tree_size(os.path.join(root, d))
        )
        for day in more:
            shutil.rmtree(os.path.join(root, day), ignore_errors=True)
        gone += more
    return gone
