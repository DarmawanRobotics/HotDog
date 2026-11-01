"""
The HTML report of one patrol.

Key figures, the points, every finding against the earlier rounds, and the evidence images
(thermal, visible, sound map, PRPD) linked from the point folders.
"""

from __future__ import annotations

import os

from hotdog_reports.core import style as s
from hotdog_reports.core.model import Patrol, Point, rank
from hotdog_reports.core.trends import earlier, key_of

EVIDENCE = (
    ('_thermal', 'Thermal'),
    ('_visible', 'Visible'),
    ('_soundmap', 'Sound map'),
    ('_prpd', 'PRPD'),
)
STATES = {'done': 'done', 'partial': 'partial', 'failed': 'failed', 'no_targets': 'no targets'}


def patrol_page(patrol: Patrol, hist: dict, title: str, robot: str) -> str:
    """Return the HTML of a patrol report."""
    summary, html_dir = patrol.summary, os.path.dirname(patrol.html)
    state = str(summary.get('state', ''))
    returned = ' · returned to the dock' if summary.get('returned') else ''
    subtitle = (
        f'{s.esc(robot)} · site <b>{s.esc(summary.get("site", ""))}</b> · route '
        f'{s.esc(os.path.basename(str(summary.get("route", ""))) or "(loaded last)")} · '
        f'{patrol.started:%Y-%m-%d %H:%M} · {s.esc(state)}{returned}'
    )
    body = [overview(patrol), points_table(patrol)]
    body += [point_section(n, p, hist, html_dir) for n, p in enumerate(patrol.points, start=1)]
    footer = (
        'Thermal limits after NETA MTS (absolute, over ambient, between similar components); '
        'partial discharge by acoustic imaging. Findings are screening results: confirm on site '
        'before switching or maintenance. <a class="noprint" href="index.html">The day</a> · '
        '<a class="noprint" href="../index.html">All days</a>'
    )
    return s.page(f'{title} — {patrol.started:%Y-%m-%d %H:%M}', subtitle, ''.join(body), footer)


def overview(patrol: Patrol) -> str:
    """Return the key figures of the patrol."""
    summary = patrol.summary
    findings = summary.get('findings', {}) or {}
    worst = str(summary.get('worst', 'normal'))
    tiles = [
        s.tile(s.badge(worst), 'worst finding'),
        s.tile(len(patrol.points), 'points inspected'),
        s.tile(findings.get('critical', 0), 'critical'),
        s.tile(findings.get('warning', 0), 'warning'),
        s.tile(findings.get('attention', 0), 'attention'),
        s.tile(s.duration(summary.get('duration_sec')), 'duration'),
    ]
    state = str(summary.get('state', ''))
    message = s.esc(summary.get('message', ''))
    return (
        f'<section><h2>Summary</h2><p class="meta"><span class="state state-{s.esc(state)}">'
        f'{s.esc(state.upper())}</span> — {message}</p>'
        f'<div class="tiles">{"".join(tiles)}</div></section>'
    )


def points_table(patrol: Patrol) -> str:
    """Return the list of the points, worst first in its own column."""
    if not patrol.points:
        return '<section><h2>Points</h2><p class="meta">No point was inspected.</p></section>'
    rows = []
    for n, p in enumerate(patrol.points, start=1):
        counts = [f for _, f in p.findings if rank(f.get('severity', '')) > 0]
        rows.append(
            f'<tr><td class="num">{n}</td><td>{s.clock(p.data.get("time", ""))}</td>'
            f'<td><a href="#p{n}">{s.esc(p.name)}</a></td>'
            f'<td>{s.esc(STATES.get(p.data.get("state", ""), p.data.get("state", "")))}</td>'
            f'<td>{s.badge(p.severity)}</td><td class="num">{len(counts)}</td></tr>'
        )
    head = '<tr><th class="num">#</th><th>Time</th><th>Point</th><th>State</th><th>Severity</th>'
    head += '<th class="num">Findings</th></tr>'
    return f'<section><h2>Points</h2>{s.table(head, rows)}</section>'


def point_section(n: int, point: Point, hist: dict, html_dir: str) -> str:
    """Return one point: its findings with the earlier rounds and its evidence."""
    d = point.data
    meta = (
        f'{s.clock(d.get("time", ""))} · x {s.number(d.get("x"), "m", 2)}, '
        f'y {s.number(d.get("y"), "m", 2)} · {s.esc(STATES.get(d.get("state", ""), ""))} · '
        f'{s.esc(d.get("message", ""))}'
    )
    rows = [finding_row(point, t, f, hist) for t, f in point.findings]
    table = ''
    if rows:
        head = (
            '<tr><th>Target</th><th>Check</th><th>Region / type</th><th class="num">Value</th>'
            '<th class="num">Reference</th><th class="num">Δ</th><th>Last round</th>'
            '<th>Severity</th><th>Note</th></tr>'
        )
        table = s.table(head, rows)
    errors = [
        f'{s.esc(t.get("target", ""))}: {s.esc(e)}'
        for t in d.get('targets', [])
        for e in t.get('errors', [])
    ]
    errors_html = f'<p class="errors">{"<br>".join(errors)}</p>' if errors else ''
    return (
        f'<section class="point" id="p{n}"><h2>{n}. {s.esc(point.name)} {s.badge(point.severity)}'
        f'</h2><p class="meta">{meta}</p>{table}{errors_html}'
        f'{evidence(point, html_dir)}</section>'
    )


def finding_row(point: Point, target: dict, f: dict, hist: dict) -> str:
    """Return one finding with its last round."""
    unit = f.get('unit', '')
    acoustic = f.get('sensor') == 'acoustic'
    key = key_of(str(point.data.get('site', '')), point.name, target.get('target', ''), f)
    last = earlier(hist, key)
    before = '<span class="meta">first round</span>'
    if last is not None:
        change = float(f.get('value', 0.0)) - last.value
        arrow = 'up' if change > 0.05 else 'down' if change < -0.05 else ''
        before = (
            f'{s.number(last.value, unit)} <span class="{arrow}">'
            f'({s.number(change, unit, sign=True)})</span><br><span class="meta">'
            f'{s.esc(last.time[:16].replace("T", " "))}, {last.rounds} earlier</span>'
        )
    reference = '—' if acoustic else s.number(f.get('reference'), unit)
    delta = '—' if acoustic else s.number(f.get('delta'), unit, sign=True)
    check = s.CRITERIA.get(f.get('criterion', ''), f.get('criterion', ''))
    return (
        f'<tr><td>{s.esc(target.get("target", ""))}</td><td>{s.esc(check)}</td>'
        f'<td>{s.esc(f.get("label", ""))}</td><td class="num">{s.number(f.get("value"), unit)}'
        f'</td><td class="num">{reference}</td><td class="num">{delta}</td><td>{before}</td>'
        f'<td>{s.badge(f.get("severity", ""))}</td><td>{s.esc(f.get("message", ""))}</td></tr>'
    )


def evidence(point: Point, html_dir: str) -> str:
    """Return the images of the point, linked relative to the report page."""
    figures = []
    for target in point.data.get('targets', []):
        for name in target.get('files', []):
            stem = os.path.splitext(str(name))[0]
            label = next((t for suffix, t in EVIDENCE if stem.endswith(suffix)), 'Image')
            path = os.path.relpath(os.path.join(point.directory, str(name)), html_dir)
            url = s.esc(path.replace(os.sep, '/'))
            caption = f'{s.esc(target.get("target", ""))} · {label}'
            figures.append(
                f'<figure><a href="{url}"><img src="{url}" alt="{caption}" loading="lazy"></a>'
                f'<figcaption>{caption}</figcaption></figure>'
            )
    return f'<div class="grid">{"".join(figures)}</div>' if figures else ''
