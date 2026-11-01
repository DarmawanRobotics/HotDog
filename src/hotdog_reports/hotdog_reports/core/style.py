"""The look of every report page: one stylesheet, the page frame and small formatters."""

from __future__ import annotations

from datetime import datetime
import html
import math

CSS = """
:root { --ink:#16202c; --muted:#5b6878; --line:#d9dee5; --bg:#f4f6f8; --head:#0f2742;
  --normal:#2e7d32; --attention:#b7860b; --warning:#e65100; --critical:#c62828; }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  color:var(--ink); background:var(--bg); }
header { background:var(--head); color:#fff; padding:18px 24px; }
header h1 { margin:0; font-size:20px; letter-spacing:.2px; }
header .sub { color:#c5d3e6; margin-top:4px; }
main { max-width:1180px; margin:0 auto; padding:16px; }
section { background:#fff; border:1px solid var(--line); border-radius:6px; padding:16px;
  margin:0 0 16px; }
h2 { font-size:16px; margin:0 0 10px; display:flex; gap:10px; align-items:center; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { background:#eef1f5; font-weight:600; white-space:nowrap; }
.scroll { overflow-x:auto; }
th.num { text-align:right; }
td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.meta { color:var(--muted); margin:0 0 10px; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
.tile { border:1px solid var(--line); border-radius:6px; padding:10px 12px; }
.tile > b { display:block; font-size:22px; min-height:30px; }
.tile > span { color:var(--muted); font-size:12px; text-transform:uppercase; }
.tile .sev { font-size:13px; padding:3px 12px; vertical-align:middle; }
.sev { display:inline-block; padding:1px 8px; border-radius:10px; color:#fff; font-size:11px;
  font-weight:700; letter-spacing:.4px; text-transform:uppercase; }
.sev-normal { background:var(--normal); } .sev-attention { background:var(--attention); }
.sev-warning { background:var(--warning); } .sev-critical { background:var(--critical); }
.state { font-weight:600; } .state-failed, .up { color:var(--critical); }
.down { color:var(--normal); }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:10px;
  margin-top:10px; }
figure { margin:0; border:1px solid var(--line); border-radius:6px; overflow:hidden;
  background:#fafbfc; }
figure img { width:100%; height:190px; object-fit:contain; background:#000; display:block; }
figcaption { padding:6px 8px; font-size:12px; color:var(--muted); }
.errors { color:var(--critical); margin:8px 0 0; }
a { color:#1659a8; text-decoration:none; } a:hover { text-decoration:underline; }
footer { color:var(--muted); font-size:12px; text-align:center; padding:8px 0 24px; }
@media (max-width:640px) { main { padding:8px; } th, td { padding:5px; } }
@media print { body { background:#fff; } header { -webkit-print-color-adjust:exact;
  print-color-adjust:exact; } section { break-inside:avoid; border:none; padding:8px 0; }
  .point { break-before:page; } .noprint { display:none; } a { color:inherit; } }
"""

UNITS = {'degC': '°C', 'degc': '°C', 'C': '°C'}
SENSORS = {'thermal': 'Thermal', 'acoustic': 'Partial discharge'}
CRITERIA = {
    'absolute': 'Absolute temperature',
    'ambient': 'Rise over ambient',
    'similar': 'Rise over similar components',
    'discharge': 'Discharge type',
}


def esc(value) -> str:
    """Return text safe in HTML."""
    return html.escape(str(value), quote=True)


def badge(severity: str) -> str:
    """Return a severity badge."""
    name = severity if severity in ('normal', 'attention', 'warning', 'critical') else 'normal'
    return f'<span class="sev sev-{name}">{esc(name)}</span>'


def number(value, unit: str = '', digits: int = 1, sign: bool = False) -> str:
    """Return a value with its unit ('—' when missing)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return '—'
    if math.isnan(v):
        return '—'
    text = f'{v:+.{digits}f}' if sign else f'{v:.{digits}f}'
    unit = UNITS.get(unit, unit)
    return f'{text} {esc(unit)}'.strip()


def clock(iso: str) -> str:
    """Return the HH:MM:SS of an ISO time ('' when unreadable)."""
    try:
        return datetime.fromisoformat(iso).strftime('%H:%M:%S')
    except (TypeError, ValueError):
        return ''


def duration(seconds) -> str:
    """Return a duration as 1 h 05 min or 4 min 10 s."""
    s = int(float(seconds or 0.0))
    if s >= 3600:
        return f'{s // 3600} h {s % 3600 // 60:02d} min'
    return f'{s // 60} min {s % 60:02d} s' if s >= 60 else f'{s} s'


def page(title: str, subtitle: str, body: str, footer: str = '') -> str:
    """Return a whole HTML page."""
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{esc(title)}</title><style>{CSS}</style></head><body>'
        f'<header><h1>{esc(title)}</h1><div class="sub">{subtitle}</div></header>'
        f'<main>{body}</main><footer>{footer}</footer></body></html>\n'
    )


def table(head: str, rows: list, empty: str = '') -> str:
    """Return a table that scrolls on its own on a phone (the empty text without rows)."""
    if not rows and empty:
        return f'<p class="meta">{esc(empty)}</p>'
    return f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>'


def tile(value, label: str) -> str:
    """Return one key figure."""
    return f'<div class="tile"><b>{value}</b><span>{esc(label)}</span></div>'
