"""
The day pages and the front page: every patrol and point of a day, every day at a glance.

    <reports_dir>/index.html            the days, newest first
    <reports_dir>/<day>/index.html      the patrols and points of a day
    <reports_dir>/<day>/day.json        the day's figures (read by the front page)
"""

from __future__ import annotations

from datetime import datetime
import os

from dharma_utils.io import read_json
from hotdog_reports.core import style as s
from hotdog_reports.core.model import (
    SEVERITIES,
    day_dirs,
    load_patrol,
    load_point,
    patrol_files,
    point_dirs,
    rank,
)


def day_figures(day_dir: str) -> dict:
    """Return the figures of a day: patrols, points, findings per severity, the worst."""
    counts = dict.fromkeys(SEVERITIES, 0)
    points, worst = 0, 'normal'
    for directory in point_dirs(day_dir):
        point = load_point(directory)
        if point is None:
            continue
        points += 1
        for _, f in point.findings:
            counts[SEVERITIES[rank(f.get('severity', ''))]] += 1
        if rank(point.severity) > rank(worst):
            worst = point.severity
    return {
        'patrols': len(patrol_files(day_dir)),
        'points': points,
        'findings': counts,
        'worst': worst,
    }


def day_page(day_dir: str, title: str, robot: str) -> str:
    """Return the HTML of a day."""
    day = os.path.basename(day_dir)
    date = f'{day[:4]}-{day[4:6]}-{day[6:]}'
    rows = []
    for path in patrol_files(day_dir):
        patrol = load_patrol(path)
        if patrol is None:
            continue
        sm = patrol.summary
        f = sm.get('findings', {}) or {}
        link = os.path.basename(patrol.html)
        rows.append(
            f'<tr><td><a href="{s.esc(link)}">{patrol.started:%H:%M:%S}</a></td>'
            f'<td>{s.esc(os.path.basename(str(sm.get("route", ""))))}</td>'
            f'<td class="state state-{s.esc(sm.get("state", ""))}">{s.esc(sm.get("state", ""))}'
            f'{" (returned)" if sm.get("returned") else ""}</td>'
            f'<td class="num">{len(patrol.points)}</td><td class="num">{f.get("critical", 0)}</td>'
            f'<td class="num">{f.get("warning", 0)}</td><td class="num">{f.get("attention", 0)}'
            f'</td><td>{s.badge(str(sm.get("worst", "normal")))}</td>'
            f'<td>{s.duration(sm.get("duration_sec"))}</td></tr>'
        )
    head = (
        '<tr><th>Start</th><th>Route</th><th>State</th><th class="num">Points</th>'
        '<th class="num">Critical</th><th class="num">Warning</th><th class="num">Attention</th>'
        '<th>Worst</th><th>Duration</th></tr>'
    )
    patrols = s.table(head, rows, 'None.')
    points = []
    for directory in point_dirs(day_dir):
        point = load_point(directory)
        if point is None:
            continue
        link = s.esc(f'{os.path.basename(directory)}/')
        points.append(
            f'<tr><td>{s.clock(point.data.get("time", ""))}</td>'
            f'<td><a href="{link}">{s.esc(point.name)}</a></td>'
            f'<td>{s.esc(point.data.get("state", ""))}</td><td>{s.badge(point.severity)}</td>'
            f'<td>{s.esc(point.data.get("message", ""))}</td></tr>'
        )
    head = '<tr><th>Time</th><th>Point</th><th>State</th><th>Severity</th><th>Note</th></tr>'
    table = s.table(head, points, 'None.')
    body = (
        f'<section><h2>Patrols</h2>{patrols}</section>'
        f'<section><h2>Inspection points</h2>{table}<p class="meta">Every finding of the day: '
        f'<a href="findings.csv">findings.csv</a></p></section>'
    )
    footer = '<a href="../index.html">All days</a>'
    return s.page(f'{title} — {date}', s.esc(robot), body, footer)


def front_page(root: str, title: str, robot: str, figures: dict) -> str:
    """Return the HTML of every day, newest first; figures: {day: day_figures()}."""
    rows = []
    for day in sorted(figures, reverse=True):
        fig = figures[day]
        f = fig.get('findings', {})
        date = f'{day[:4]}-{day[4:6]}-{day[6:]}'
        rows.append(
            f'<tr><td><a href="{day}/index.html">{date}</a></td>'
            f'<td class="num">{fig.get("patrols", 0)}</td>'
            f'<td class="num">{fig.get("points", 0)}</td>'
            f'<td class="num">{f.get("critical", 0)}</td><td class="num">{f.get("warning", 0)}'
            f'</td><td class="num">{f.get("attention", 0)}</td>'
            f'<td>{s.badge(fig.get("worst", "normal"))}</td></tr>'
        )
    head = (
        '<tr><th>Day</th><th class="num">Patrols</th><th class="num">Points</th>'
        '<th class="num">Critical</th><th class="num">Warning</th><th class="num">Attention</th>'
        '<th>Worst</th></tr>'
    )
    body = s.table(head, rows, 'No reports yet.')
    updated = datetime.now().strftime('%Y-%m-%d %H:%M')
    return s.page(title, f'{s.esc(robot)} · updated {updated}', f'<section>{body}</section>')


def read_figures(root: str) -> dict:
    """Return {day: figures} of every day from its day.json (computed when missing)."""
    out = {}
    for day in day_dirs(root):
        data, _error = read_json(os.path.join(root, day, 'day.json'))
        out[day] = data if isinstance(data, dict) else day_figures(os.path.join(root, day))
    return out
