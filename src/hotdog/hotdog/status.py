"""
The robot at a glance, as text.

One line per part (patrol, health, localization, control, battery, inspection, navigation,
alerts, reports) from plain values, so it is tested without ROS: `ros2 run hotdog status`
collects the values (status_cli.py), `scripts/hotdog.sh status` prints them.
"""

from __future__ import annotations

PATROL = ('IDLE', 'STARTING', 'RUNNING', 'DONE', 'FAILED', 'STOPPED', 'RETURNING')
HEALTH = ('OK', 'WARN', 'ERROR')
LOCALIZATION = ('NONE', 'LOCALIZED', 'UNCERTAIN')
INSPECTION = ('IDLE', 'INSPECTING', 'DISABLED')
NAVIGATION = (
    'INACTIVE', 'JOINING', 'FOLLOWING', 'APPROACHING', 'DWELLING', 'PAUSED', 'BLOCKED',
    'OFF_PATH', 'GOAL_REACHED', 'FAILED',
)  # fmt: skip
FIELD = ('OFF', 'CLEAR', 'LIMITED', 'STOP', 'STALE', 'BLIND')
SEVERITY = ('normal', 'attention', 'warning', 'critical')
BAD = {'FAILED', 'ERROR', 'NONE', 'BLOCKED', 'OFF_PATH', 'STOP', 'STALE', 'BLIND', 'critical'}
WARN = {'WARN', 'UNCERTAIN', 'RETURNING', 'PAUSED', 'LIMITED', 'warning', 'STOPPED'}
MISSING = '(no message: is hotdog running? sudo systemctl status hotdog)'


def name(table: tuple, value) -> str:
    """Return the name of a state number ('?' when unknown)."""
    try:
        return table[int(value)]
    except (IndexError, TypeError, ValueError):
        return '?'


def paint(text: str, color: bool) -> str:
    """Color a state by how bad it is (ANSI) when color is on."""
    if not color:
        return text
    code = '31' if text in BAD else '33' if text in WARN else '32'
    return f'\x1b[{code}m{text}\x1b[0m'


def patrol(p: dict) -> tuple:
    """Return the state and details of patrol/status."""
    minutes = f'{int(p.get("elapsed_sec") or 0) // 60} min' if p.get('elapsed_sec') else ''
    counts = f'points {p["points"]} (C{p["critical"]} W{p["warning"]} A{p["attention"]})'
    nxt = f'next {p["next_scheduled"]}' if p.get('next_scheduled') else 'no schedule'
    message = f'— {p["message"]}' if p.get('message') else ''
    return name(PATROL, p['state']), p.get('route', ''), minutes, counts, nxt, message


def inspection(i: dict) -> tuple:
    """Return the state and details of inspection/status."""
    pod = 'pod ok' if i['pod_connected'] else 'POD MISSING'
    acoustic = 'acoustic ok' if i['acoustic_connected'] else 'ACOUSTIC MISSING'
    worst = name(SEVERITY, i['last_severity'])
    last = f'last {i["last_point"]} {worst}' if i['last_point'] else ''
    size = f'{i["points"]} points {i["targets"]} targets'
    return (
        name(INSPECTION, i['state']),
        pod,
        acoustic,
        f'ambient {i["ambient_c"]:.1f} °C',
        size,
        last,
    )


def parts(s: dict) -> list[tuple]:
    """Return (label, state, details...) of every part; '?' for what was not received."""
    h, loc, c, n = (s.get(k) for k in ('health', 'localization', 'control', 'navigation'))
    b = s.get('battery')
    out = [('patrol', *patrol(s['patrol'])) if s.get('patrol') else ('patrol', '?', MISSING)]
    out.append(
        (
            'health',
            name(HEALTH, h['level']),
            f'speed {h["speed_scale"]:.0%}',
            '; '.join(h['issues']),
        )
        if h
        else ('health', '?')
    )
    out.append(
        ('localize', name(LOCALIZATION, loc['state']),
         f'({loc["source"]}) drift ±{loc["sigma_xy"]:.2f} m') if loc else ('localize', '?')
    )  # fmt: skip
    if c:
        estop = 'E-STOP ' + ','.join(c['estop_reasons']) if c['estop'] else 'e-stop off'
        out.append(('control', 'REMOTE' if c['mode'] else 'AUTO', estop,
                    f'field {name(FIELD, c["field"])}'))  # fmt: skip
    else:
        out.append(('control', '?'))
    out.append(('battery', f'{b:.0%}' if b is not None and b >= 0.0 else '?'))
    i = s.get('inspection')
    out.append(('inspection', *inspection(i)) if i else ('inspection', '?'))
    out.append(
        ('navigation', name(NAVIGATION, n['state']), ','.join(n['pause_reasons']),
         f'{n["remaining"]:.0f} m left' if n['count'] else '') if n else ('navigation', '?')
    )  # fmt: skip
    return out


def lines(s: dict, color: bool = False) -> list[str]:
    """Return the status lines of a snapshot {part: {field: value} or None (not received)}."""
    out = []
    for label, state, *details in parts(s):
        text = ' '.join(d for d in details if d)
        out.append(f'{label:<11} {paint(state, color)}  {text}'.rstrip())
    for extra in ('alerts', 'reports', 'disk'):
        if s.get(extra):
            out.append(f'{extra:<11} {s[extra]}')
    return out
