"""
alert_node: what an operator must know, sent to Telegram and a webhook as it happens.

A finding at or above findings.min_severity (with its thermal image or sound map), a patrol
that failed, was stopped, came back to the dock on its own or finished, a robot whose health
is ERROR. Alerts are spooled on disk and retried until the uplink is back; the Telegram bot
token comes from $TELEGRAM_BOT_TOKEN and the webhook's bearer from $HOTDOG_WEBHOOK_TOKEN.
"""

from __future__ import annotations

import os
import time

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from std_srvs.srv import Trigger

from dharma_interfaces.msg import HealthStatus
from dharma_utils.io import expand, read_json
from dharma_utils.ros import EVENTS, LATCHED, DharmaNode, run
from hotdog_alerts.core import events
from hotdog_alerts.core.channels import Telegram, Webhook
from hotdog_alerts.core.config import AlertsConfig
from hotdog_alerts.core.dispatch import Dispatcher
from hotdog_alerts.core.spool import Spool
from hotdog_alerts.core.text import words
from hotdog_interfaces.msg import InspectionReport, PatrolStatus

STATES = {
    PatrolStatus.DONE: 'done',
    PatrolStatus.FAILED: 'failed',
    PatrolStatus.STOPPED: 'stopped',
}
SEVERITY = ('normal', 'attention', 'warning', 'critical')
HEALTH_ERROR = 2


class AlertNode(DharmaNode):
    """Turns events into alerts and sends them."""

    def __init__(self, **kwargs):
        super().__init__('alert_node', **kwargs)
        self.config = self.declare_config(AlertsConfig)
        cfg = self.config.value
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        telegram = Telegram(token, cfg.timeout_sec) if token else None
        url = cfg.webhook.url.strip()
        hook_token = os.environ.get('HOTDOG_WEBHOOK_TOKEN', '').strip()
        webhook = Webhook(url, hook_token, cfg.timeout_sec) if url else None
        self.spool = Spool(expand(cfg.spool_dir))
        self.dispatcher = Dispatcher(self.spool, telegram, webhook, cfg.robot_name)
        self.memory = events.Memory()
        self.patrols: set = set()  # patrol summaries announced (or seen at start)
        self.first_patrol = True
        events_group = MutuallyExclusiveCallbackGroup()
        sub = self.create_subscription
        sub(InspectionReport, 'inspection/report', self.on_report, EVENTS,
            callback_group=events_group)  # fmt: skip
        sub(PatrolStatus, 'patrol/status', self.on_patrol, LATCHED, callback_group=events_group)
        sub(HealthStatus, 'health/status', self.on_health, LATCHED, callback_group=events_group)
        self.create_service(Trigger, 'alerts/test', self.srv_test, callback_group=events_group)
        self.every(cfg.retry_sec, self.flush, group=MutuallyExclusiveCallbackGroup())
        channels = self.dispatcher.channels(cfg.telegram.chat_ids)
        if not channels:
            self.log.warning('no alert channel: set TELEGRAM_BOT_TOKEN and telegram.chat_ids, '
                             'or webhook.url')  # fmt: skip
        self.log.info('alerts', channels=','.join(c.split(':')[0] for c in channels),
                      queued=len(self.spool.files()))  # fmt: skip

    # ---------------------------------------------------------------- events
    def on_report(self, msg: InspectionReport):
        """Announce the findings of an inspected point."""
        cfg = self.config.value
        if not cfg.enabled or not msg.directory:
            return
        report, error = read_json(os.path.join(msg.directory, 'report.json'))
        if not isinstance(report, dict):
            self.log.error('report not read', directory=msg.directory, error=str(error))
            return
        for alert in events.finding_alerts(report, msg.directory, cfg, self.memory, time.time()):
            self.queue(alert)

    def on_patrol(self, msg: PatrolStatus):
        """Announce a patrol that ended (not one that had ended before this node started)."""
        first, self.first_patrol = self.first_patrol, False
        state = STATES.get(msg.state)
        if state is None or not msg.report or msg.report in self.patrols:
            return
        self.patrols.add(msg.report)
        cfg = self.config.value
        if first or not cfg.enabled:
            return
        status = {
            'state': state, 'site': msg.site, 'route': os.path.basename(msg.route),
            'message': msg.message, 'points': msg.points, 'critical': msg.critical,
            'warning': msg.warning, 'attention': msg.attention, 'returned': msg.returned,
            'worst': SEVERITY[min(3, int(msg.worst))],
        }  # fmt: skip
        link = events.report_link(cfg.report_url, expand(cfg.reports_dir), msg.report)
        alert = events.patrol_alert(status, cfg, link)
        if alert is not None:
            self.queue(alert)

    def on_health(self, msg: HealthStatus):
        """Announce a health ERROR (repeated only after health_repeat_min)."""
        cfg = self.config.value
        if not cfg.enabled or msg.level < HEALTH_ERROR:
            return
        if self.memory.health_due(time.time(), cfg.health_repeat_min * 60.0):
            self.queue(events.health_alert(msg.level, msg.issues, cfg))

    def srv_test(self, _request, response):
        """Service: queue a test alert to every channel."""
        cfg = self.config.value
        title = words(cfg.language)['test'].format(robot=cfg.robot_name)
        response.success = bool(self.queue(events.Alert('test', 'normal', title)))
        response.message = 'queued' if response.success else 'no alert channel configured'
        return response

    # ---------------------------------------------------------------- sending
    def queue(self, alert: events.Alert) -> str:
        """Spool an alert for every channel."""
        channels = self.dispatcher.channels(self.config.value.telegram.chat_ids)
        try:
            path = self.spool.put(alert, channels, time.time())
        except OSError as error:
            self.log.error('alert not queued', title=alert.title, error=str(error))
            return ''
        self.log.info('alert', kind=alert.kind, severity=alert.severity, title=alert.title,
                      channels=len(channels))  # fmt: skip
        return path

    def flush(self):
        """Send what is queued; drop what is too old or too much."""
        cfg = self.config.value
        dropped = self.spool.trim(time.time(), cfg.max_age_hours * 3600.0, cfg.max_queued)
        if dropped:
            self.log.error('alerts dropped unsent', count=len(dropped))
        result = self.dispatcher.flush()
        for channel, error in result.failed.items():
            self.log.warning('alert not sent', channel=channel.split(':')[0], error=error,
                             queued=result.left, throttle=60.0)  # fmt: skip


def main(args=None):
    """Run alert_node."""
    run(AlertNode, args=args, threads=2)


if __name__ == '__main__':
    main()
