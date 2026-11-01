"""What is announced, the words, the spool and the channels (no ROS)."""

from __future__ import annotations

import os

from fake_api import FakeApi
from hotdog_alerts.core import events
from hotdog_alerts.core.channels import Telegram, Webhook, telegram_text
from hotdog_alerts.core.config import AlertsConfig
from hotdog_alerts.core.dispatch import Dispatcher
from hotdog_alerts.core.spool import Spool
import pytest

from dharma_utils.config import build


def cfg(**overrides) -> AlertsConfig:
    return build(AlertsConfig, {'robot_name': 'HotDog 01', **overrides})


def report(hot: float = 95.0, discharge: str = 'noise', severity: str = 'warning') -> dict:
    return {
        'site': 'gi', 'point': 'bay1', 'state': 'done', 'severity': severity,
        'targets': [{
            'target': 'bay1_clamps',
            'files': ['bay1_clamps_visible.jpg', 'bay1_clamps_thermal.jpg'],
            'findings': [
                {'sensor': 'thermal', 'criterion': 'similar', 'label': 's', 'severity': severity,
                 'value': hot, 'reference': 80.0, 'delta': hot - 80.0, 'unit': 'degC'},
                {'sensor': 'acoustic', 'criterion': 'discharge', 'label': discharge,
                 'severity': 'critical' if discharge == 'floating' else 'normal', 'value': 41.0,
                 'reference': 0.0, 'delta': 0.0, 'unit': 'dB'},
            ],
        }],
    }  # fmt: skip


def test_findings_at_or_above_the_minimum_with_their_image(tmp_path):
    (tmp_path / 'bay1_clamps_thermal.jpg').write_bytes(b'\xff\xd8\xff\xd9')
    memory = events.Memory()
    alerts = events.finding_alerts(report(), str(tmp_path), cfg(), memory, 0.0)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.severity == 'warning' and a.title == '🟠 WARNING at bay1'
    assert 'bay1_clamps (s): 95.0 °C, +15.0 °C over the other phases' in a.lines
    assert a.lines[-1] == 'Plan a repair.'
    assert a.image.endswith('bay1_clamps_thermal.jpg')  # preferred over the visible one
    quiet = events.finding_alerts(report(severity='attention'), str(tmp_path), cfg(), memory, 0.0)
    assert quiet == []  # below warning


def test_repeats_are_quiet_unless_worse(tmp_path):
    memory, c = events.Memory(), cfg()
    assert events.finding_alerts(report(), str(tmp_path), c, memory, 0.0)
    assert not events.finding_alerts(report(), str(tmp_path), c, memory, 3600.0)
    worse = events.finding_alerts(report(discharge='floating'), str(tmp_path), c, memory, 3600.0)
    assert (
        worse
        and worse[0].severity == 'critical'
        and 'floating partial discharge' in worse[0].text()
    )
    assert events.finding_alerts(report(), str(tmp_path), c, memory, 13 * 3600.0)


def test_bahasa_indonesia():
    a = events.finding_alerts(report(discharge='floating'), '/x', cfg(language='id'),
                              events.Memory(), 0.0)[0]  # fmt: skip
    assert a.title == '🔴 KRITIS di bay1'
    assert a.lines[-1] == 'Segera laporkan ke petugas gardu induk.'
    assert 'di atas fasa lain' in a.text()


def test_patrol_alerts():
    status = {'state': 'done', 'site': 'gi', 'route': 'r1.csv', 'message': 'end', 'points': 4,
              'critical': 1, 'warning': 0, 'attention': 2, 'returned': False,
              'worst': 'critical'}  # fmt: skip
    done = events.patrol_alert(status, cfg(), 'http://robot:8088/20261101/patrol_090000.html')
    assert done.title == '🔴 Patrol done: 4 points, worst CRITICAL'
    assert '1 critical · 0 warning · 2 attention' in done.lines
    assert done.text().endswith('patrol_090000.html')
    assert events.patrol_alert(status, cfg(patrol_done=False)) is None
    failed = events.patrol_alert({**status, 'state': 'failed', 'message': 'lost'}, cfg())
    assert failed.severity == 'critical' and 'FAILED: lost' in failed.title
    back = events.patrol_alert({**status, 'state': 'failed', 'returned': True,
                                'message': 'back at the dock: battery 15%'}, cfg())  # fmt: skip
    assert back.title.startswith('↩️ Back at the dock')
    assert events.patrol_alert({**status, 'state': 'running'}, cfg()) is None


def test_health_and_links():
    memory = events.Memory()
    assert memory.health_due(0.0, 1800.0) and not memory.health_due(60.0, 1800.0)
    assert memory.health_due(1801.0, 1800.0)
    alert = events.health_alert(2, ['sensor /lidar/points stale'], cfg())
    assert 'ERROR: sensor /lidar/points stale' in alert.title
    link = events.report_link('http://10.0.0.5:8088/', '/r', '/r/20261101/patrol_090000.json')
    assert link == 'http://10.0.0.5:8088/20261101/patrol_090000.html'
    assert events.report_link('', '/r', '/r/x.json') == ''
    assert events.report_link('http://h/', '/r', '/etc/patrol.json') == ''


def test_the_spool_keeps_what_is_not_sent(tmp_path):
    spool = Spool(str(tmp_path / 'spool'))
    alert = events.Alert('test', 'normal', 'hello')
    assert spool.put(alert, [], 1.0) == ''
    first = spool.put(alert, ['telegram:1', 'webhook'], 1.0)
    spool.put(alert, ['webhook'], 2.0)
    assert spool.files()[0] == first
    loaded, entry = spool.load(first)
    assert loaded == alert and entry['pending'] == ['telegram:1', 'webhook']
    assert spool.trim(1.0 + 48 * 3600 + 1, 48 * 3600.0, 500) == [first]
    spool.put(alert, ['webhook'], 3.0)
    assert len(spool.trim(4.0, 48 * 3600.0, 1)) == 1 and len(spool.files()) == 1
    broken = os.path.join(spool.directory, '0000000000005_9.json')
    with open(broken, 'w') as f:
        f.write('{')
    assert spool.load(broken) == (None, None) and not os.path.exists(broken)


@pytest.fixture
def api():
    server = FakeApi()
    yield server
    server.stop()


def test_telegram_and_webhook_deliver_and_retry(tmp_path, api):
    image = tmp_path / 'bay1_clamps_thermal.jpg'
    image.write_bytes(b'\xff\xd8\xff\xd9')
    telegram = Telegram('TOKEN', 5.0, base=api.base + '/bot{token}/{method}')
    webhook = Webhook(api.base + '/hook', 'secret', 5.0)
    spool = Spool(str(tmp_path / 'spool'))
    dispatcher = Dispatcher(spool, telegram, webhook, 'HotDog 01')
    channels = dispatcher.channels(['-100', ''])
    assert channels == ['telegram:-100', 'webhook']
    spool.put(
        events.Alert('finding', 'critical', '🔴 <b>x</b>', ['a & b'], str(image)), channels, 1.0
    )
    spool.put(events.Alert('test', 'normal', 'plain'), channels, 2.0)
    api.status = 502
    result = dispatcher.flush()
    assert result.sent == 0 and set(result.failed) == set(channels) and result.left == 2
    assert len(api.requests) == 2  # each failing channel tried once per pass
    api.status, api.requests = 200, []
    result = dispatcher.flush()
    assert result.sent == 4 and result.left == 0
    paths = [r['path'] for r in api.requests]
    assert paths == ['/botTOKEN/sendPhoto', '/hook', '/botTOKEN/sendMessage', '/hook']
    photo = api.requests[0]
    assert photo['type'].startswith('multipart/form-data') and b'\xff\xd8' in photo['body']
    assert b'&lt;b&gt;x&lt;/b&gt;' in photo['body'] and b'a &amp; b' in photo['body']
    hook = api.requests[1]
    assert hook['auth'] == 'Bearer secret' and hook['json']['robot'] == 'HotDog 01'
    assert hook['json']['severity'] == 'critical'
    assert api.requests[2]['json']['text'] == '<b>plain</b>'


def test_telegram_text_escapes():
    text = telegram_text(events.Alert('x', 'normal', 'a<b', ['c>d'], link='http://h/?a=1&b=2'))
    assert text == '<b>a&lt;b</b>\nc&gt;d\nhttp://h/?a=1&amp;b=2'
