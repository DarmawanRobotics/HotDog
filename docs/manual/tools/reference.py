"""
Generate the reference tables of the manual from the Dharma sources.

    python3 docs/manual/tools/reference.py --src <dir with the dharma_* checkouts>

Parameters come from the configuration dataclasses (dharma_utils.config.entries), so names,
defaults, units, ranges and descriptions are exactly what the nodes declare. Messages and
services come from dharma_interfaces/msg and srv. Output: docs/manual/generated/*.tex.
Needs Python 3.10+ and numpy (the controller modules import it).
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parents[1] / 'generated'

# package roots relative to --src, added to sys.path
ROOTS = [
    'dharma_utils',
    'dharma_odometry',
    'dharma_localization',
    'dharma_perception',
    'dharma_mapping',
    'dharma_navigation/dharma_navigation',
    'dharma_navigation/dharma_control',
    'dharma_health',
    'dharma_sim',
]

# table name -> list of (node, module, class, prefix)
TABLES = {
    'robot': [('every node', 'dharma_utils.robot', 'RobotProfile', 'robot.')],
    'odometry': [
        ('odometry_gate (wait_still)', 'dharma_odometry.core.config', 'StillConfig', ''),
        ('odometry_monitor_node', 'dharma_odometry.core.config', 'MonitorConfig', ''),
    ],
    'localization': [
        ('localization_node', 'dharma_localization.core.config', 'LocalizationConfig', ''),
    ],
    'perception': [
        ('lidar_sector_node', 'dharma_perception.core.config', 'PerceptionConfig', ''),
        ('aruco_detector_node', 'dharma_perception.core.aruco', 'ArucoConfig', ''),
    ],
    'mapping': [
        ('grid_mapper_node', 'dharma_mapping.core.config', 'MapperConfig', ''),
        ('site_manager_node', 'dharma_mapping.core.config', 'SiteConfig', ''),
        ('route_recorder_node', 'dharma_mapping.core.config', 'RecorderConfig', ''),
    ],
    'navigation': [
        ('planner_node', 'dharma_navigation.core.config.planner', 'PlannerConfig', ''),
        ('path_loader_node', 'dharma_navigation.core.config.loader', 'LoaderConfig', ''),
        ('path_follower_node', 'dharma_navigation.core.config.follower', 'FollowerConfig', ''),
        (
            'obstacle_avoidance_node',
            'dharma_navigation.core.config.avoidance',
            'AvoidanceConfig',
            '',
        ),
    ],
    'docking': [
        ('docking_node', 'dharma_navigation.core.config.docking', 'DockingConfig', ''),
    ],
    'controllers': [
        (
            f'path_follower_node: {name}',
            f'dharma_navigation.core.controllers.{module}',
            cls,
            f'{name}.',
        )
        for name, module, cls in [
            ('holonomic', 'holonomic', 'HolonomicConfig'),
            ('pure_pursuit', 'pure_pursuit', 'PurePursuitConfig'),
            ('pid', 'pid', 'PidConfig'),
            ('lqr', 'lqr', 'LqrConfig'),
            ('stanley', 'stanley', 'StanleyConfig'),
            ('mppi', 'mppi', 'MppiConfig'),
        ]
    ],
    'control': [
        ('control_mux_node', 'dharma_control.core.config', 'MuxConfig', ''),
        ('control_mux_node', 'dharma_control.core.config', 'FieldConfig', 'field.'),
    ],
    'health': [
        ('health_monitor_node', 'dharma_health.core.config', 'HealthConfig', ''),
    ],
    'sim': [
        ('sim_robot_node', 'dharma_sim.core.config', 'SimConfig', ''),
    ],
}

SPECIAL = {
    '\\': r'\textbackslash{}',
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_\allowbreak{}',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
}


def tex(text: str) -> str:
    """Escape plain text for LaTeX."""
    return ''.join(SPECIAL.get(c, c) for c in str(text))


def unit(text: str) -> str:
    """Typeset a unit such as m/s^2."""
    text = re.sub(r'\\textasciicircum\{\}(\d)', r'$^{\1}$', tex(text))
    return text.replace('/', r'/\allowbreak{}')


def value(v) -> str:
    """Typeset a default value."""
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        return f'{v:g}'
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(value(x) for x in v) + ']'
    if isinstance(v, str):
        if ' ' in v:
            return r'\texttt{' + tex(v) + '}'
        return r'\code{' + v + '}' if v else r'\code{""}'
    return tex(v)


def span(spec) -> str:
    """Typeset the range or the choices of a parameter."""
    if spec.choices:
        return ', '.join(tex(c) for c in spec.choices)
    lo = '' if spec.min is None else f'{spec.min:g}'
    hi = '' if spec.max is None or spec.max > 1e6 else f'{spec.max:g}'
    return f'{lo}..{hi}' if lo or hi else ''


def param_table(rows) -> str:
    """Return one longtable of parameter entries."""
    head = (
        '\\begin{small}\n\\begin{longtable}{@{}>{\\raggedright}p{0.25\\textwidth}'
        '>{\\raggedright}p{0.17\\textwidth}>{\\raggedright}p{0.10\\textwidth}'
        '>{\\raggedright}p{0.11\\textwidth}>{\\raggedright\\arraybackslash}p{0.25\\textwidth}@{}}'
        '\n\\toprule\n'
        'Parameter & Default & Unit & Range & Description \\\\\n\\midrule\n\\endhead\n'
        '\\bottomrule\n\\endfoot\n'
    )
    body = []
    for node, items in rows:
        body.append(f'\\multicolumn{{5}}{{@{{}}l}}{{\\textbf{{{tex(node)}}}}} \\\\\n')
        for e in items:
            mark = r'$^\dagger$' if not e.spec.live else ''
            body.append(
                f'\\code{{{e.name}}}{mark} & {value(e.default)} & {unit(e.spec.unit)} & '
                f'{span(e.spec)} & {tex(e.spec.doc)} \\\\\n'
            )
    return head + ''.join(body) + '\\end{longtable}\n\\end{small}\n'


def write_params():
    """Write generated/params_<table>.tex for every table."""
    from dharma_utils.config import entries

    for table, specs in TABLES.items():
        rows = []
        for node, module, cls, prefix in specs:
            config = getattr(importlib.import_module(module), cls)
            rows.append((node, entries(config, prefix)))
        (OUT / f'params_{table}.tex').write_text(
            '% Generated by docs/manual/tools/reference.py; do not edit.\n' + param_table(rows),
            encoding='utf-8',
        )


def parse_interface(path: Path):
    """Return (constants, sections of fields) of a .msg or .srv file."""
    constants, sections, fields = [], [], []
    for raw in path.read_text(encoding='utf-8').splitlines():
        if raw.strip() == '---':
            sections.append(fields)
            fields = []
            continue
        line, _, comment = raw.partition('#')
        parts = line.split()
        if len(parts) < 2:
            continue
        if '=' in line:
            name, _, val = ' '.join(parts[1:]).partition('=')
            constants.append((parts[0], name.strip(), val.strip(), comment.strip()))
        else:
            fields.append((parts[0], parts[1], comment.strip()))
    sections.append(fields)
    return constants, sections


def interface_block(path: Path) -> str:
    """Return a table for one interface."""
    constants, sections = parse_interface(path)
    kind = 'msg' if path.suffix == '.msg' else 'srv'
    out = [
        f'\\subsection*{{\\texorpdfstring{{\\code{{{path.stem}}}}}{{{path.stem}}} ({kind})}}\n',
        (
            '\\begin{small}\n\\begin{tabularx}{\\textwidth}{@{}p{0.25\\textwidth}'
            'p{0.25\\textwidth}X@{}}\n\\toprule\n'
        ),
    ]
    if constants:
        out.append('\\multicolumn{3}{@{}l}{\\emph{constants}} \\\\\n')
        for typ, name, val, comment in constants:
            out.append(f'\\code{{{name}}} = {tex(val)} & \\code{{{typ}}} & {tex(comment)} \\\\\n')
    titles = ['request', 'response'] if kind == 'srv' else ['fields']
    if len(titles) != len(sections):
        raise ValueError(f'{path.name}: {len(sections)} sections, expected {len(titles)}')
    for title, fields in zip(titles, sections):
        out.append(f'\\multicolumn{{3}}{{@{{}}l}}{{\\emph{{{title}}}}} \\\\\n')
        if not fields:
            out.append('\\multicolumn{3}{@{}l}{(empty)} \\\\\n')
        for typ, name, comment in fields:
            out.append(f'\\code{{{name}}} & \\code{{{typ}}} & {tex(comment)} \\\\\n')
    out.append('\\bottomrule\n\\end{tabularx}\n\\end{small}\n')
    return ''.join(out)


def write_interfaces(src: Path):
    """Write generated/interfaces.tex from dharma_interfaces."""
    root = src / 'dharma_interfaces'
    parts = ['% Generated by docs/manual/tools/reference.py; do not edit.\n']
    for folder, title in (('msg', 'Messages'), ('srv', 'Services')):
        parts.append(f'\\section{{{title}}}\n')
        for path in sorted((root / folder).glob(f'*.{folder}')):
            parts.append(interface_block(path))
    (OUT / 'interfaces.tex').write_text(''.join(parts), encoding='utf-8')


def main():
    """Parse arguments and write every generated file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('--src', required=True, type=Path, help='dir with dharma_* checkouts')
    args = parser.parse_args()
    for root in ROOTS:
        sys.path.insert(0, str(args.src / root))
    OUT.mkdir(parents=True, exist_ok=True)
    write_params()
    write_interfaces(args.src)


if __name__ == '__main__':
    main()
