"""Patrol pages, trends, the day and front pages, the builder (no ROS)."""

from __future__ import annotations

from datetime import datetime
import json
import os

from hotdog_reports.core import index, render
from hotdog_reports.core.build import Builder
from hotdog_reports.core.model import day_dirs, load_patrol, patrol_files, point_dirs
from hotdog_reports.core.style import duration, number
from hotdog_reports.core.trends import earlier, history
from tree import point, two_rounds


def test_patrols_and_their_points(tmp_path):
    first, second = two_rounds(str(tmp_path))
    listed = load_patrol(first)
    assert [p.name for p in listed.points] == ['bay1', 'bay2']
    guessed = load_patrol(second)  # an older summary without its inspections
    assert [p.name for p in guessed.points] == ['bay1', 'bay2']
    assert guessed.points[0].severity == 'critical'
    assert day_dirs(str(tmp_path)) == ['20261031', '20261101']
    assert len(point_dirs(str(tmp_path / '20261101'))) == 2
    assert patrol_files(str(tmp_path / '20261101')) == [second]
    (tmp_path / 'broken.json').write_text('{')
    assert load_patrol(str(tmp_path / 'broken.json')) is None


def test_findings_are_compared_with_the_last_round(tmp_path):
    two_rounds(str(tmp_path))
    hist = history(str(tmp_path), datetime(2026, 11, 1, 9, 0, 0), 30)
    last = earlier(hist, ('gi', 'bay1', 'bay1_clamps', 'absolute', 's'))
    assert (last.value, last.rounds, last.time) == (85.0, 1, '2026-10-31T09:02:00')
    assert earlier(hist, ('gi', 'bay9', 'x', 'absolute', 's')) is None
    assert history(str(tmp_path), datetime(2026, 11, 1, 9, 0, 0), 0) == {}
    later = history(str(tmp_path), datetime(2026, 11, 2), 30)  # both rounds before it
    assert later[('gi', 'bay1', 'bay1_clamps', 'absolute', 's')][-1][1] == 91.5


def test_the_patrol_page(tmp_path):
    _, second = two_rounds(str(tmp_path))
    patrol = load_patrol(second)
    hist = history(str(tmp_path), patrol.started, 30)
    page = render.patrol_page(patrol, hist, 'GI Cawang', 'HotDog 01')
    assert page.startswith('<!doctype html>')
    assert 'GI Cawang — 2026-11-01 09:00' in page
    assert 'sev-critical' in page and 'floating' in page
    assert '91.5 °C' in page and '+6.5 °C' in page  # 85.0 on the last round
    assert 'href="090200_bay1/bay1_clamps_thermal.jpg"' in page
    assert page.count('class="point"') == 2


def test_names_are_escaped(tmp_path):
    folder = point(str(tmp_path), datetime(2026, 11, 1, 10, 0, 0), 'x<script>', 50.0)
    data = json.loads(
        (tmp_path / '20261101' / os.path.basename(folder) / 'report.json').read_text()
    )
    data['message'] = '<img src=x onerror=alert(1)>'
    (tmp_path / '20261101' / os.path.basename(folder) / 'report.json').write_text(json.dumps(data))
    page = index.day_page(str(tmp_path / '20261101'), 'T', 'R')
    assert '<script>' not in page and '&lt;script&gt;' in page
    assert '<img src=x' not in page


def test_day_and_front_pages(tmp_path):
    two_rounds(str(tmp_path))
    figures = index.day_figures(str(tmp_path / '20261101'))
    assert figures['patrols'] == 1 and figures['points'] == 2
    assert figures['worst'] == 'critical' and figures['findings']['warning'] == 1
    front = index.front_page(str(tmp_path), 'T', 'R', index.read_figures(str(tmp_path)))
    assert front.index('2026-11-01') < front.index('2026-10-31')  # newest first
    day = index.day_page(str(tmp_path / '20261101'), 'T', 'R')
    assert 'patrol_090000.html' in day and 'findings.csv' in day


def test_the_builder_renders_once_and_on_demand(tmp_path):
    first, second = two_rounds(str(tmp_path))
    builder = Builder(str(tmp_path), 'GI Cawang', 'HotDog 01', 30)
    assert sorted(builder.missing()) == sorted([first, second])
    page = builder.patrol(second)
    assert os.path.isfile(page) and page.endswith('patrol_090000.html')
    assert (tmp_path / '20261101' / 'index.html').is_file()
    assert (tmp_path / '20261101' / 'day.json').is_file()
    assert (tmp_path / 'index.html').is_file()
    assert builder.missing() == [first]
    assert builder.rebuild() == (1, [])
    assert builder.missing() == []
    assert builder.rebuild(everything=True) == (2, [])
    (tmp_path / '20261101' / 'patrol_120000.json').write_text('[]')
    pages, errors = builder.rebuild()
    assert pages == 0 and len(errors) == 1


def test_formatting():
    assert number(87.26, 'degC') == '87.3 °C'
    assert number(3.0, 'degC', sign=True) == '+3.0 °C'
    assert number(None) == '—' and number(float('nan')) == '—'
    assert duration(65) == '1 min 05 s' and duration(3725) == '1 h 02 min'
    assert duration(9) == '9 s'
