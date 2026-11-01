"""A reports folder as inspection_node and patrol_node write it: two rounds of one route."""

from __future__ import annotations

import csv
from datetime import datetime
import json
import os

FIELDS = (
    'time', 'site', 'point', 'target', 'sensor', 'criterion', 'label', 'severity',
    'value', 'reference', 'delta', 'unit', 'message', 'report',
)  # fmt: skip
RANKS = ['normal', 'attention', 'warning', 'critical']


def point(root, when: datetime, name: str, hottest: float, discharge: str = 'noise') -> str:
    """Write a point's report.json, its images and its findings rows; return its folder."""
    day = os.path.join(root, when.strftime('%Y%m%d'))
    folder = os.path.join(day, f'{when:%H%M%S}_{name}')
    os.makedirs(folder)
    severity = 'warning' if hottest >= 90.0 else 'normal'
    thermal = {
        'sensor': 'thermal', 'criterion': 'absolute', 'label': 's', 'severity': severity,
        'value': hottest, 'reference': 30.0, 'delta': hottest - 30.0, 'unit': 'degC',
        'message': f'hottest {hottest} degC',
    }  # fmt: skip
    acoustic = {
        'sensor': 'acoustic', 'criterion': 'discharge', 'label': discharge,
        'severity': 'critical' if discharge == 'floating' else 'normal', 'value': 42.0,
        'reference': 0.0, 'delta': 0.0, 'unit': 'dB', 'message': discharge,
    }  # fmt: skip
    files = [f'{name}_clamps_thermal.jpg', f'{name}_clamps_visible.jpg']
    report = {
        'time': when.isoformat(timespec='seconds'), 'site': 'gi', 'point': name, 'x': 3.0,
        'y': -1.5, 'state': 'done',
        'severity': max((thermal['severity'], acoustic['severity']), key=RANKS.index),
        'duration_sec': 20.0, 'message': f'{name}: 1/1 targets measured',
        'targets': [{'target': f'{name}_clamps', 'measured': True, 'errors': [],
                     'files': files, 'findings': [thermal, acoustic]}],
    }  # fmt: skip
    with open(os.path.join(folder, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f)
    for name_ in files:
        with open(os.path.join(folder, name_), 'wb') as f:
            f.write(b'\xff\xd8\xff\xd9')
    table = os.path.join(day, 'findings.csv')
    new = not os.path.isfile(table)
    with open(table, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for finding in (thermal, acoustic):
            writer.writerow({'time': report['time'], 'site': 'gi', 'point': name,
                             'target': f'{name}_clamps', 'report': os.path.basename(folder),
                             **finding})  # fmt: skip
    return folder


def patrol(root, started: datetime, folders: list, worst: str, listed: bool = True) -> str:
    """Write a patrol summary; listed: with its inspections (else an older summary)."""
    summary = {
        'site': 'gi', 'route': 'gi/routes/2026-11-01_09-30-00.csv',
        'started': started.timestamp(), 'duration_sec': 600.0, 'state': 'done',
        'message': 'the end of the route was reached', 'points': len(folders),
        'findings': {'normal': 1, 'attention': 0, 'warning': 1, 'critical': 0},
        'worst': worst, 'returned': False,
    }  # fmt: skip
    if listed:
        summary['inspections'] = folders
    path = os.path.join(root, started.strftime('%Y%m%d'), f'patrol_{started:%H%M%S}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(summary, f)
    return path


def two_rounds(root) -> tuple[str, str]:
    """Return the summaries of yesterday's and today's round (bay1 hotter today)."""
    y = datetime(2026, 10, 31, 9, 0, 0)
    a = [
        point(root, y.replace(minute=2), 'bay1', 85.0),
        point(root, y.replace(minute=5), 'bay2', 50.0),
    ]
    first = patrol(root, y, a, 'normal')
    t = datetime(2026, 11, 1, 9, 0, 0)
    b = [point(root, t.replace(minute=2), 'bay1', 91.5, 'floating'),
         point(root, t.replace(minute=5), 'bay2', 49.0)]  # fmt: skip
    second = patrol(root, t, b, 'critical', listed=False)
    return first, second
