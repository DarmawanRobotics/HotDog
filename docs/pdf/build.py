#!/usr/bin/env python3
"""
Build the PDF guides from their Markdown sources.

    pip install weasyprint markdown pyyaml       # macOS: brew install pango first
    python3 docs/pdf/build.py                    # every guide
    python3 docs/pdf/build.py manual             # one of: manual, technician, acceptance

Pages are A5, which reads well on a phone. Text is Barlow Semi Condensed (docs/pdf/fonts, SIL
Open Font License). A source starts with a YAML front matter (title, subtitle, version, date,
revisions) and may contain `{{ parameter_reference }}`, replaced by tables of every parameter in
the packages' config files, read with their comments.
"""

from __future__ import annotations

import html
from pathlib import Path
import re
import sys

import markdown
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration
import yaml

DOCS = Path(__file__).resolve().parents[1]
ROOT = DOCS.parent
GUIDES = {
    'manual': (DOCS / 'manual' / 'user-manual.md', DOCS / 'HotDog-User-Manual.pdf'),
    'technician': (
        DOCS / 'technician' / 'technician-guide.md',
        DOCS / 'HotDog-Technician-Guide.pdf',
    ),
    'acceptance': (
        DOCS / 'acceptance' / 'acceptance-test.md',
        DOCS / 'HotDog-Site-Acceptance-Test.pdf',
    ),
}

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


def front_matter(text: str) -> tuple:
    """Return (metadata, body) of a source with a --- YAML --- header."""
    if not text.startswith('---\n'):
        return {}, text
    end = text.index('\n---\n', 4)
    return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]


def number_headings(body: str) -> tuple:
    """Give h1 (1) and h2 (1.1) headings their numbers; return the HTML and the contents."""
    chapter, section, entries = 0, 0, []

    def number(match):
        nonlocal chapter, section
        level, attrs, text = int(match[1]), match[2], match[3]
        if 'unnumbered' in attrs:
            entries.append((level, '', re.search(r'id="([^"]+)"', attrs)[1], text))
            return match[0]
        if level == 1:
            chapter, section = chapter + 1, 0
            label = f'{chapter}'
        else:
            section += 1
            label = f'{chapter}.{section}'
        anchor = re.search(r'id="([^"]+)"', attrs)[1]
        entries.append((level, label, anchor, text))
        return f'<h{level}{attrs}><span class="num">{label}</span> {text}</h{level}>'

    body = re.sub(r'<h([12])([^>]*)>(.*?)</h\1>', number, body)
    return body, entries


def figures(body: str) -> str:
    """Turn a paragraph holding only an image into a figure with its alt text as caption."""

    def figure(match):
        tag = match[1]
        alt = re.search(r'alt="([^"]*)"', tag)
        css = re.search(r'class="([^"]*)"', tag)
        caption = f'<figcaption>{alt[1]}</figcaption>' if alt and alt[1] else ''
        return f'<figure class="{css[1] if css else ""}">{tag}{caption}</figure>'

    return re.sub(r'<p>\s*(<img [^>]+>)\s*</p>', figure, body)


def build(name: str):
    """Render one guide to its PDF."""
    source, target = GUIDES[name]
    meta, text = front_matter(source.read_text())
    text = text.replace('{{ parameter_reference }}', parameter_reference())
    body = markdown.markdown(
        text,
        extensions=[
            'tables',
            'attr_list',
            'admonition',
            'toc',
            'fenced_code',
            'md_in_html',
            'sane_lists',
        ],
        extension_configs={'toc': {'permalink': False}},
    )
    body, entries = number_headings(figures(body))
    contents = '\n'.join(
        f'<li class="toc{level}"><a href="#{anchor}"><span class="num">{label}</span> '
        f'{re.sub("<[^>]+>", "", text)}</a></li>'
        for level, label, anchor, text in entries
    )
    revisions = '\n'.join(
        f'<tr><td>{html.escape(str(v))}</td><td>{html.escape(str(d))}</td>'
        f'<td>{html.escape(str(n))}</td></tr>'
        for v, d, n in meta.get('revisions', [])
    )
    title = html.escape(meta.get('title', name))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
</head><body>
<section class="cover">
  <img class="logo" src="{(DOCS / 'logo.png').as_uri()}" alt="">
  <div class="brand">HOTDOG</div>
  <h1 class="cover-title unnumbered">{title}</h1>
  <p class="cover-subtitle">{html.escape(meta.get('subtitle', ''))}</p>
  <p class="cover-version">Version {html.escape(str(meta.get('version', '')))} ·
     {html.escape(str(meta.get('date', '')))}</p>
  <p class="cover-for">{html.escape(meta.get('audience', ''))}</p>
</section>
<section class="front">
  <h2 class="front-title">Revision history</h2>
  <table class="revisions"><thead><tr><th>Version</th><th>Date</th><th>Changes</th></tr></thead>
  <tbody>{revisions}</tbody></table>
  <p class="front-note">{html.escape(meta.get('note', ''))}</p>
</section>
<section class="front contents">
  <h2 class="front-title">Contents</h2>
  <ul class="toc">{contents}</ul>
</section>
<main>{body}</main>
</body></html>"""
    css = (
        (Path(__file__).parent / 'style.css')
        .read_text()
        .replace('%HEADER%', meta.get('header', meta.get('title', '')))
    )
    fonts = FontConfiguration()  # loads the @font-face fonts of the stylesheet
    HTML(string=page, base_url=str(source.parent)).write_pdf(
        target,
        stylesheets=[CSS(string=css, base_url=str(Path(__file__).parent), font_config=fonts)],
        font_config=fonts,
    )
    print(f'{target.relative_to(ROOT)}: {len(entries)} sections')


if __name__ == '__main__':
    for guide in sys.argv[1:] or GUIDES:
        build(guide)
