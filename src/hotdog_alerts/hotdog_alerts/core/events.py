"""
What deserves an alert, as plain data.

A finding at or above the configured severity, a patrol that ended (failures always), a robot
whose health is ERROR.

The inputs are the dicts of report.json and the fields of the status messages, so everything
here is tested without ROS. Memory keeps repeats quiet: the same finding again only after
findings.repeat_hours unless it got worse, health ERROR again only after health_repeat_min.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os

from hotdog_alerts.core.config import SEVERITIES, AlertsConfig
from hotdog_alerts.core.text import ICONS, words

EVIDENCE = ('_thermal', '_soundmap', '_visible', '_prpd')  # preferred image first


@dataclass
class Alert:
    """One message for every channel."""

    kind: str  # finding | patrol | health | test
    severity: str  # normal ... critical
    title: str
    lines: list = field(default_factory=list)
    image: str = ''  # a file on the robot
    link: str = ''
    data: dict = field(default_factory=dict)

    def text(self) -> str:
        """Return the plain text (title, lines, link)."""
        out = [self.title, *self.lines]
        return '\n'.join(out + ([self.link] if self.link else []))


def rank(severity: str) -> int:
    """Return the order of a severity name (unknown: normal)."""
    return SEVERITIES.index(severity) if severity in SEVERITIES else 0


class Memory:
    """When each finding and the health were last announced."""

    def __init__(self):
        self.findings: dict = {}  # key -> (time, rank)
        self.health_at = -1e18

    def finding_due(self, key: tuple, severity: int, now: float, repeat_sec: float) -> bool:
        """Return whether a finding is announced now (and remember it)."""
        last = self.findings.get(key)
        if last is not None and severity <= last[1] and now - last[0] < repeat_sec:
            return False
        self.findings[key] = (now, severity)
        return True

    def health_due(self, now: float, repeat_sec: float) -> bool:
        """Return whether health ERROR is announced now (and remember it)."""
        if now - self.health_at < repeat_sec:
            return False
        self.health_at = now
        return True


def finding_alerts(report: dict, directory: str, cfg: AlertsConfig, memory: Memory, now: float):
    """Return one alert per announced target of a point's report.json."""
    w, minimum = words(cfg.language), rank(cfg.findings.min_severity)
    site, point = str(report.get('site', '')), str(report.get('point', ''))
    out = []
    for target in report.get('targets', []):
        name = str(target.get('target', ''))
        found = [f for f in target.get('findings', []) if rank(f.get('severity', '')) >= minimum]
        due = [
            f
            for f in found
            if memory.finding_due(
                (site, point, name, f.get('criterion', ''), f.get('label', '')),
                rank(f.get('severity', '')),
                now,
                cfg.findings.repeat_hours * 3600.0,
            )
        ]
        if not due:
            continue
        worst = max((str(f.get('severity', 'normal')) for f in due), key=rank)
        lines = [f'{cfg.robot_name} · {w["site"]} {site}']
        lines += [describe(w, name, f) for f in due]
        lines.append(w['act'].get(worst, ''))
        title = f'{ICONS[worst]} ' + w['finding'].format(sev=w[worst], point=point)
        image = pick_image(directory, target.get('files', [])) if cfg.telegram.photos else ''
        data = {'site': site, 'point': point, 'target': name, 'findings': due}
        out.append(Alert('finding', worst, title, lines, image, data=data))
    return out


def describe(w: dict, target: str, f: dict) -> str:
    """Return one finding as a line."""
    value = round(float(f.get('value', 0.0)), 1)
    label = f.get('label', '')
    if f.get('sensor') == 'acoustic':
        return w['acoustic'].format(target=target, label=label, value=value)
    criterion = f.get('criterion', '')
    if criterion in ('ambient', 'similar'):
        ref = w['ref_ambient'] if criterion == 'ambient' else w['ref_similar']
        delta = float(f.get('delta', 0.0))
        return w['thermal'].format(target=target, label=label, value=value, delta=delta,
                                   ref_name=ref)  # fmt: skip
    return w['absolute'].format(target=target, label=label, value=value)


def pick_image(directory: str, files) -> str:
    """Return the best evidence image of a target ('' when none exists)."""
    names = [str(n) for n in files]
    for suffix in EVIDENCE:
        for name in names:
            path = os.path.join(directory, name)
            if os.path.splitext(name)[0].endswith(suffix) and os.path.isfile(path):
                return path
    return ''


def patrol_alert(status: dict, cfg: AlertsConfig, link: str = '') -> Alert | None:
    """Return the alert of a patrol that ended (state done, failed or stopped)."""
    w, state = words(cfg.language), status.get('state', '')
    if state == 'done' and not cfg.patrol_done:
        return None
    worst = str(status.get('worst', 'normal'))
    message = str(status.get('message', ''))
    if status.get('returned'):
        title, severity = f'↩️ {w["returned"].format(message=message)}', 'warning'
    elif state == 'failed':
        title, severity = f'⛔ {w["failed"].format(message=message)}', 'critical'
    elif state == 'stopped':
        title, severity = f'⏹ {w["stopped"].format(message=message)}', 'attention'
    elif state == 'done':
        done = w['done'].format(points=status.get('points', 0), worst=w.get(worst, worst))
        title = f'{ICONS.get(worst, "")} {done}'
        severity = worst
    else:
        return None
    lines = [
        f'{cfg.robot_name} · {w["site"]} {status.get("site", "")} · {status.get("route", "")}',
        w['counts'].format(**{k: status.get(k, 0) for k in ('critical', 'warning', 'attention')}),
    ]
    return Alert('patrol', severity, title.strip(), lines, link=link, data=dict(status))


def health_alert(level: int, issues, cfg: AlertsConfig) -> Alert:
    """Return the alert of a health ERROR."""
    w = words(cfg.language)
    text = '; '.join(issues) or '—'
    return Alert('health', 'critical', f'🛑 {w["health"].format(issues=text)}',
                 [cfg.robot_name], data={'level': level, 'issues': list(issues)})  # fmt: skip


def report_link(base: str, reports_dir: str, summary: str) -> str:
    """Return the URL of a patrol page from the summary path ('' without a base)."""
    if not base or not summary:
        return ''
    rel = os.path.relpath(os.path.splitext(summary)[0] + '.html', reports_dir)
    if rel.startswith('..'):
        return ''
    return base.rstrip('/') + '/' + rel.replace(os.sep, '/')
