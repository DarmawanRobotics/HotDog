"""
Alerts waiting to be sent, on disk.

A substation's uplink drops and the robot restarts: an alert must still arrive.

    <spool_dir>/<unix ms>_<n>.json   {"alert": {...}, "pending": ["telegram:<chat>", "webhook"],
                                      "created": <unix s>, "attempts": n, "error": "..."}

Each channel is sent once; a file goes when no channel is pending. Too old or too many: the
oldest are dropped (and reported).
"""

from __future__ import annotations

import contextlib
from dataclasses import asdict
import os
import re

from dharma_utils.io import read_json, write_json_atomic
from hotdog_alerts.core.events import Alert

NAME_RE = re.compile(r'^\d{13}_\d+\.json$')


class Spool:
    """A folder of alerts, oldest first."""

    def __init__(self, directory: str):
        self.directory = directory
        self.count = 0

    def put(self, alert: Alert, channels: list[str], now: float) -> str:
        """Queue an alert for channels; return its file ('' without channels)."""
        if not channels:
            return ''
        os.makedirs(self.directory, exist_ok=True)
        self.count += 1
        path = os.path.join(self.directory, f'{int(now * 1000):013d}_{self.count}.json')
        entry = {'alert': asdict(alert), 'pending': list(channels), 'created': now,
                 'attempts': 0, 'error': ''}  # fmt: skip
        write_json_atomic(path, entry, backup=False)
        return path

    def files(self) -> list[str]:
        """Return the queued files, oldest first."""
        if not os.path.isdir(self.directory):
            return []
        return [
            os.path.join(self.directory, n)
            for n in sorted(os.listdir(self.directory))
            if NAME_RE.match(n)
        ]

    def load(self, path: str):
        """Return (Alert, entry) of a file, (None, None) when unreadable (it is removed)."""
        entry, _error = read_json(path)
        try:
            alert = Alert(**entry['alert'])
            return alert, entry
        except (TypeError, KeyError):
            self.remove(path)
            return None, None

    def update(self, path: str, entry: dict):
        """Write back the pending channels, or remove the file when none is left."""
        if entry['pending']:
            write_json_atomic(path, entry, backup=False)
        else:
            self.remove(path)

    def trim(self, now: float, max_age_sec: float, max_files: int) -> list[str]:
        """Drop alerts older than max_age_sec, then the oldest beyond max_files."""
        dropped = []
        files = self.files()
        for path in files:
            created = int(os.path.basename(path).split('_')[0]) / 1000.0
            if now - created > max_age_sec:
                dropped.append(path)
        left = [p for p in files if p not in dropped]
        dropped += left[: max(0, len(left) - max_files)]
        for path in dropped:
            self.remove(path)
        return dropped

    def remove(self, path: str):
        """Remove a file (gone already is fine)."""
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)
