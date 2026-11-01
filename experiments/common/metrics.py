"""Metrics of the runs and the CSV files of the results."""

from __future__ import annotations

import csv
from dataclasses import asdict, fields, is_dataclass
import math
from pathlib import Path

import numpy as np

from dharma_utils.math import Pose2D
from dharma_utils.robot import Footprint

RESULTS = Path(__file__).resolve().parents[1] / 'results'


def box_clearance(footprint: Footprint, pose: Pose2D, circles: np.ndarray) -> float:
    """Return the smallest distance (m) from the footprint at pose to the circle surfaces."""
    circles = np.asarray(circles, dtype=float).reshape(-1, 4)
    if not len(circles):
        return math.inf
    local = pose.inverse().apply(circles[:, :2])
    lo = np.array([-footprint.rear, -footprint.half_width])
    hi = np.array([footprint.front, footprint.half_width])
    nearest = np.clip(local, lo, hi)
    gap = np.hypot(*(local - nearest).T) - circles[:, 2]
    inside = np.all((local >= lo) & (local <= hi), axis=1)
    return float(np.where(inside, -circles[:, 2], gap).min())


def summary(values) -> dict:
    """Return n, mean, std (sample), median, min and max of the finite values."""
    v = np.asarray([x for x in values if x is not None and math.isfinite(x)], dtype=float)
    if not len(v):
        return {'n': 0, 'mean': math.nan, 'std': math.nan, 'median': math.nan,
                'min': math.nan, 'max': math.nan}  # fmt: skip
    std = float(v.std(ddof=1)) if len(v) > 1 else 0.0
    return {'n': len(v), 'mean': float(v.mean()), 'std': std, 'median': float(np.median(v)),
            'min': float(v.min()), 'max': float(v.max())}  # fmt: skip


def write_rows(name: str, rows: list, directory: Path = RESULTS) -> Path:
    """Write dataclass rows (or dicts) to <directory>/<name>.csv; return the path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{name}.csv'
    dicts = [asdict(r) if is_dataclass(r) else dict(r) for r in rows]
    header = [f.name for f in fields(rows[0])] if is_dataclass(rows[0]) else list(dicts[0])
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator='\n')
        writer.writeheader()
        for row in dicts:
            writer.writerow({k: _cell(v) for k, v in row.items()})
    return path


def read_rows(name: str, directory: Path = RESULTS) -> list[dict]:
    """Read <directory>/<name>.csv as dicts of strings."""
    with open(directory / f'{name}.csv', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def _cell(value):
    if isinstance(value, float):
        return 'inf' if math.isinf(value) else f'{value:.6g}'
    return value
