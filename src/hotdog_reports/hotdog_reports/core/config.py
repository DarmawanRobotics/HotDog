"""Configuration of report_node: rendering, trends, retention, the report server."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_utils.config import nested, param


@dataclass(frozen=True)
class RetentionConfig:
    """What is deleted, oldest day first (never today)."""

    days: int = param(365, min=0, max=3650, unit='d', doc='delete days older than this (0: keep)')
    min_free_gb: float = param(
        5.0, min=0.0, max=1000.0, unit='GB', doc='delete the oldest days while less is free'
    )
    period_min: float = param(60.0, min=1.0, max=1440.0, unit='min', doc='how often to check')


@dataclass(frozen=True)
class ServerConfig:
    """The reports over HTTP on the robot's network, read-only."""

    enabled: bool = param(True, live=False, doc='serve reports_dir at http://<robot>:<port>/')
    host: str = param('0.0.0.0', live=False, doc='address to listen on (127.0.0.1: this computer)')
    port: int = param(8088, min=1, max=65535, live=False, doc='TCP port')


@dataclass(frozen=True)
class ReportsConfig:
    """Everything report_node reads."""

    reports_dir: str = param('~/.hotdog/reports', live=False, doc='<day>/ of the inspections')
    title: str = param('HotDog substation patrol', doc='heading of every report')
    robot_name: str = param('HotDog', doc='the robot named in the reports')
    trend_days: int = param(
        30, min=0, max=365, unit='d', doc='earlier findings each finding is compared with'
    )
    retention: RetentionConfig = nested(RetentionConfig)
    server: ServerConfig = nested(ServerConfig)
