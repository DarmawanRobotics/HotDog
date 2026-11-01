"""Retention by age and free space, and the read-only report server (no ROS)."""

from __future__ import annotations

from datetime import date
import urllib.error
import urllib.request

from hotdog_reports.core.retention import expired, prune, to_free
from hotdog_reports.utils.server import ReportServer
import pytest

TODAY = date(2026, 11, 1)


def test_old_days_expire():
    days = ['20251031', '20251101', '20261031', '20261101']
    assert expired(days, TODAY, 365) == ['20251031']
    assert expired(days, TODAY, 0) == []


def test_space_is_freed_oldest_first_never_today():
    days = ['20261029', '20261030', '20261031', '20261101']
    sizes = {'20261029': 5, '20261030': 5, '20261031': 5, '20261101': 100}
    assert to_free(days, TODAY, free=0, need=8, size=sizes.get) == ['20261029', '20261030']
    assert to_free(days, TODAY, free=10, need=8, size=sizes.get) == []
    assert to_free(days, TODAY, free=0, need=1000, size=sizes.get) == days[:3]


def test_prune_deletes_the_folders(tmp_path):
    for day in ('20241231', '20261031', '20261101'):
        (tmp_path / day).mkdir()
        (tmp_path / day / 'findings.csv').write_text('x' * 10)
    (tmp_path / 'notes').mkdir()  # not a day: never touched
    assert prune(str(tmp_path), TODAY, 365, 0.0) == ['20241231']
    assert prune(str(tmp_path), TODAY, 0, 1e9) == ['20261031']  # never enough: all but today
    assert sorted(p.name for p in tmp_path.iterdir()) == ['20261101', 'notes']
    assert prune(str(tmp_path / 'missing'), TODAY, 365, 5.0) == []


@pytest.fixture
def server(tmp_path):
    (tmp_path / 'index.html').write_text('<h1>reports</h1>')
    (tmp_path / '20261101').mkdir()
    srv = ReportServer(str(tmp_path / '20261101'), '127.0.0.1', 0)
    srv.start()
    yield srv, tmp_path
    srv.stop()


def test_the_server_reads_files_and_nothing_else(server):
    srv, tmp_path = server
    (tmp_path / '20261101' / 'index.html').write_text('<h1>day</h1>')
    base = f'http://127.0.0.1:{srv.port}'
    with urllib.request.urlopen(f'{base}/index.html', timeout=5) as r:
        assert r.status == 200 and b'day' in r.read()
        assert r.headers['Cache-Control'] == 'no-store'
    with urllib.request.urlopen(f'{base}/../index.html', timeout=5) as r:
        assert b'day' in r.read()  # '..' never leaves the folder
    with pytest.raises(urllib.error.HTTPError) as missing:
        urllib.request.urlopen(f'{base}/nothing.html', timeout=5)
    assert missing.value.code == 404
    request = urllib.request.Request(f'{base}/index.html', data=b'x', method='POST')
    with pytest.raises(urllib.error.HTTPError) as post:
        urllib.request.urlopen(request, timeout=5)
    assert post.value.code == 501
