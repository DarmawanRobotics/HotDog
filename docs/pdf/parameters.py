#!/usr/bin/env python3
"""
The parameter reference of the Technician Guide and the docs site.

Every parameter of the packages' config files, with its default and the comment beside it in
the file. Python standard library only, so the docs site builds without WeasyPrint.

    python3 docs/pdf/parameters.py           # Markdown, for the docs site
    python3 docs/pdf/parameters.py --html    # HTML, as docs/pdf/build.py puts it in the PDF
"""

from __future__ import annotations

import html
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]

# Config files of the parameter reference, in reading order: (package, file, what it covers)
PARAMETER_FILES = [
    ('hotdog', 'robot.yaml', 'robot profile: footprint, limits, base height, frames'),
    ('hotdog', 'm20_driver.yaml', 'the M20 driver as HotDog runs it'),
    ('hotdog', 'stack.yaml', 'the Dharma stack as tuned for HotDog: odometry only'),
    ('hotdog_base', 'base.yaml', 'both Airy as one leveled cloud'),
    ('hotdog_inspection', 'inspection.yaml', 'overheat analysis and partial discharge'),
    ('hotdog_patrol', 'patrol.yaml', 'patrols, the watchdog, the schedule'),
    ('hotdog_reports', 'reports.yaml', 'report pages, retention, the report server'),
    ('hotdog_alerts', 'alerts.yaml', 'Telegram and webhook alerts'),
]

KEY_LINE = re.compile(r'^(?P<indent> *)(?P<key>[A-Za-z0-9_./*]+):\s*(?P<rest>.*)$')

# Meanings of parameters whose config line has no comment, by node and name
MEANINGS = {
    ('/**', 'robot.name'): 'name of the robot profile',
    ('/**', 'robot.frames.map'): 'TF frame name',
    ('/**', 'robot.frames.odom'): 'TF frame name',
    ('/**', 'robot.frames.base'): 'TF frame name',
    ('report_node', 'retention.period_min'): 'min between two retention checks',
    ('report_node', 'server.port'): 'TCP port of the report server',
    ('alert_node', 'health_repeat_min'): 'min, health ERROR announced again only after this',
    ('alert_node', 'max_queued'): 'alerts kept waiting at most; the oldest are dropped',
}


def split_comment(text: str) -> tuple:
    """Return (value, comment) of the text after 'key:', minding # inside quotes."""
    quote = None
    for i, char in enumerate(text):
        if char in '"\'' and quote in (None, char):
            quote = None if quote else char
        elif char == '#' and quote is None and (i == 0 or text[i - 1] in ' \t'):
            return text[:i].strip(), text[i + 1 :].strip()
    return text.strip(), ''


def take_comment(stripped: str, indent: int, last, node, pending: str) -> str:
    """Add a comment line to the parameter above (a run-on) or to the pending description."""
    text = ' '.join(stripped.lstrip('#').split())
    if last is not None and indent > last['indent'] + 4 and last['description']:
        last['description'] += ' ' + text  # a comment running on from the line above
        return pending
    if node is None:
        return pending
    if pending and re.match(r'[a-z_]+:\s', text) and pending[-1] not in ':;,.':
        pending += ';'  # the next item of a list like "path_shift: …  reactive: …"
    return f'{pending} {text}'.strip()


def read_parameters(path: Path) -> dict:
    """Return {node: [(name, default, description)]} of a ROS 2 parameter file, comments kept."""
    nodes: dict = {}
    node, stack, pending, last = None, [], '', None
    lines = path.read_text().splitlines()
    for number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            pending = ''
            continue
        indent = len(line) - len(line.lstrip(' '))
        if stripped.startswith('#'):
            pending = take_comment(stripped, indent, last, node, pending)
            continue
        if stripped.startswith('- '):
            if last is not None and last['list']:
                last['items'].append(split_comment(stripped[2:])[0])
            continue
        match = KEY_LINE.match(line)
        if not match:
            continue
        key, (value, comment) = match['key'], split_comment(match['rest'])
        if indent == 0:
            node, stack, pending, last = key, [], '', None
            nodes.setdefault(node, [])
            continue
        if key == 'ros__parameters':
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        following = lines[number + 1].strip() if number + 1 < len(lines) else ''
        if not value and not following.startswith('- '):
            stack.append((indent, key))  # a nested mapping (e.g. detector:)
            continue
        name = '.'.join([k for _, k in stack] + [key])
        last = {
            'indent': indent,
            'description': comment or pending,
            'list': not value,
            'items': [],
            'name': name,
            'value': value,
        }
        nodes[node].append(last)
        pending = ''
    return {
        node: [
            (
                p['name'],
                p['value'] if not p['list'] else '[' + ', '.join(p['items']) + ']',
                p['description'],
            )
            for p in params
        ]
        for node, params in nodes.items()
    }


def meaning(node: str, param: str, comment: str) -> str:
    """Return what a parameter does: its config comment, or a known meaning."""
    if comment:
        return comment
    if (node, param) in MEANINGS:
        return MEANINGS[node, param]
    if param.rsplit('.', 1)[-1].endswith('_frame'):
        return 'TF frame name'
    return ''


def breakable(text: str) -> str:
    """Escape text for HTML, with line break chances after . _ / and , (no characters added)."""
    return re.sub(r'([._/,])', r'\1<wbr>', html.escape(text))


def parameter_reference() -> str:
    """Return HTML tables of every parameter of the packages, grouped by package and node."""
    parts = []
    for package, name, what in PARAMETER_FILES:
        path = ROOT / 'src' / package / 'config' / name
        anchor = f'ref-{package}-{name}'.replace('_', '-').replace('.', '-')
        parts.append(
            f'<h2 id="{anchor}">{package} · {html.escape(name)}</h2>\n'
            f'<p class="source">{html.escape(what)} · <code>src/{package}/config/{name}</code></p>'
        )
        for node, params in read_parameters(path).items():
            rows = '\n'.join(
                f'<tr><td><code>{breakable(param)}</code></td>'
                f'<td><code>{breakable(default)}</code></td>'
                f'<td>{html.escape(meaning(node, param, description))}</td></tr>'
                for param, default, description in params
            )
            parts.append(
                f'<h3 class="node">{html.escape(node)}</h3>\n<table class="params">'
                '<thead><tr><th>Parameter</th><th>Default</th><th>Meaning</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>'
            )
    return '\n\n'.join(parts)  # one raw HTML block each for Markdown


def cell(text: str) -> str:
    """Escape text for a Markdown table cell of the docs site."""
    for char, escaped in (('\\', '\\\\'), ('|', '\\|'), ('*', '\\*'), ('_', '\\_')):
        text = text.replace(char, escaped)
    return html.escape(text, quote=False).replace('{', '&#123;')


def row(node: str, param: str, default: str, comment: str) -> str:
    """Return one parameter as a Markdown table row."""
    shown = default or "''"
    return f'| `{param}` | `{shown}` | {cell(meaning(node, param, comment))} |'


def markdown_reference() -> str:
    """Return the parameter reference as Markdown: a section per file, a table per node."""
    parts = []
    for package, name, what in PARAMETER_FILES:
        path = ROOT / 'src' / package / 'config' / name
        anchor = f'ref-{package}-{name}'.replace('_', '-').replace('.', '-')
        source = f'`src/{package}/config/{name}`'
        parts.append(f'## {package} · {name} {{#{anchor}}}\n\n{what} · {source}')
        for node, params in read_parameters(path).items():
            rows = [row(node, *param) for param in params]
            table = '| Parameter | Default | Meaning |\n| --- | --- | --- |\n' + '\n'.join(rows)
            parts.append(f'### {cell(node)}\n\n{table}')
    return '\n\n'.join(parts)


if __name__ == '__main__':
    print(parameter_reference() if '--html' in sys.argv[1:] else markdown_reference())
