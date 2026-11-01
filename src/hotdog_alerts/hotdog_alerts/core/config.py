"""Configuration of alert_node: what is announced, to whom, and how it is retried."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_utils.config import nested, param

SEVERITIES = ('normal', 'attention', 'warning', 'critical')


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram: the bot token comes from $TELEGRAM_BOT_TOKEN, never from a parameter."""

    chat_ids: tuple[str, ...] = param(('',), doc='chats or groups to send to (empty: none)')
    photos: bool = param(True, doc='attach the evidence image of a finding')


@dataclass(frozen=True)
class WebhookConfig:
    """A JSON POST per alert (SCADA, a ticket system); bearer from $HOTDOG_WEBHOOK_TOKEN."""

    url: str = param('', doc='https://... to POST to (empty: none)')


@dataclass(frozen=True)
class FindingsConfig:
    """Which findings are announced."""

    min_severity: str = param('warning', choices=SEVERITIES[1:], doc='lowest one announced')
    repeat_hours: float = param(
        12.0, min=0.0, max=720.0, unit='h', doc='the same finding again only after this, or worse'
    )


@dataclass(frozen=True)
class AlertsConfig:
    """Everything alert_node reads."""

    enabled: bool = param(True, doc='live: false queues nothing')
    language: str = param('en', choices=('en', 'id'), doc='en | id (Bahasa Indonesia)')
    robot_name: str = param('HotDog', doc='the robot named in every alert')
    report_url: str = param(
        '', doc='http://<robot>:8088/ as operators reach it (adds the patrol page link)'
    )
    reports_dir: str = param('~/.hotdog/reports', live=False, doc='where the patrol pages are')
    spool_dir: str = param('~/.hotdog/alerts', live=False, doc='alerts waiting to be sent')
    patrol_done: bool = param(True, doc='announce every finished patrol (failures always)')
    health_repeat_min: float = param(
        30.0, min=1.0, max=1440.0, unit='min', doc='health ERROR again only after this'
    )
    retry_sec: float = param(15.0, min=2.0, max=600.0, unit='s', doc='sending period')
    max_age_hours: float = param(
        48.0, min=1.0, max=720.0, unit='h', doc='an alert not sent by then is dropped'
    )
    max_queued: int = param(500, min=10, max=100000, doc='oldest dropped beyond this')
    timeout_sec: float = param(10.0, min=1.0, max=60.0, unit='s', doc='one request')
    telegram: TelegramConfig = nested(TelegramConfig)
    webhook: WebhookConfig = nested(WebhookConfig)
    findings: FindingsConfig = nested(FindingsConfig)
