"""
report_node: the HTML reports of HotDog, kept and served on the robot.

When a patrol ends (patrol/status with its summary) its page is rendered with every point,
finding, the earlier rounds and the evidence images; each inspection report refreshes its
day's page. The reports folder is pruned by age and free space, and served read-only over
HTTP so an operator opens http://<robot>:8088/ in a browser on the substation network.
"""

from __future__ import annotations

from datetime import date
import os

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from std_srvs.srv import Trigger

from dharma_utils.io import expand
from dharma_utils.ros import EVENTS, LATCHED, DharmaNode, run
from hotdog_interfaces.msg import InspectionReport, PatrolStatus
from hotdog_reports.core.build import Builder
from hotdog_reports.core.config import ReportsConfig
from hotdog_reports.core.retention import prune
from hotdog_reports.utils.server import ReportServer

ENDED = (PatrolStatus.DONE, PatrolStatus.FAILED, PatrolStatus.STOPPED)


class ReportNode(DharmaNode):
    """Renders, prunes and serves the reports."""

    def __init__(self, **kwargs):
        super().__init__('report_node', **kwargs)
        self.config = self.declare_config(ReportsConfig)
        cfg = self.config.value
        self.root = expand(cfg.reports_dir)
        self.rendered: set = set()  # patrol summaries rendered by this run
        group = MutuallyExclusiveCallbackGroup()
        sub = self.create_subscription
        sub(PatrolStatus, 'patrol/status', self.on_patrol, LATCHED, callback_group=group)
        sub(InspectionReport, 'inspection/report', self.on_report, EVENTS, callback_group=group)
        self.create_service(Trigger, 'reports/rebuild', self.srv_rebuild, callback_group=group)
        self.every(cfg.retention.period_min * 60.0, self.prune, group=group)
        self.server = None
        if cfg.server.enabled:
            self.serve()
        self.first = self.every(2.0, self.first_pass, group=group)

    def builder(self) -> Builder:
        """Return a builder with the live settings."""
        cfg = self.config.value
        return Builder(self.root, cfg.title, cfg.robot_name, cfg.trend_days)

    def serve(self):
        """Start the HTTP server (a port in use is logged, the node runs on)."""
        cfg = self.config.value.server
        try:
            os.makedirs(self.root, exist_ok=True)
            self.server = ReportServer(self.root, cfg.host, cfg.port)
        except OSError as error:
            self.log.error('report server not started', port=cfg.port, error=str(error))
            return
        self.server.start()
        self.add_shutdown_hook(self.server.stop)
        self.log.info('reports served', url=f'http://{cfg.host}:{self.server.port}/')

    def first_pass(self):
        """Once after start: render what is missing and prune."""
        self.first.cancel()
        self.rebuild(everything=False)
        self.prune()

    # ---------------------------------------------------------------- inputs
    def on_patrol(self, msg: PatrolStatus):
        """Render a patrol once it ended."""
        if msg.state not in ENDED or not msg.report or msg.report in self.rendered:
            return
        self.rendered.add(msg.report)
        try:
            page = self.builder().patrol(msg.report)
        except (OSError, ValueError) as error:
            self.log.error('patrol report not rendered', summary=msg.report, error=str(error))
            return
        self.log.info('patrol report', page=page, worst=msg.worst)

    def on_report(self, msg: InspectionReport):
        """Refresh the day of an inspection report."""
        if not msg.directory:
            return
        try:
            self.builder().day(os.path.dirname(msg.directory))
        except OSError as error:
            self.log.error('day page not rendered', directory=msg.directory, error=str(error))

    # ---------------------------------------------------------------- upkeep
    def srv_rebuild(self, _request, response):
        """Service: render every page again."""
        pages, errors = self.rebuild(everything=True)
        response.success = not errors
        response.message = f'{pages} patrol pages' + (f'; {"; ".join(errors)}' if errors else '')
        return response

    def rebuild(self, everything: bool) -> tuple[int, list[str]]:
        """Render the missing (or every) page."""
        try:
            pages, errors = self.builder().rebuild(everything)
        except OSError as error:
            return 0, [str(error)]
        if pages or errors:
            self.log.info('reports rendered', pages=pages, errors=len(errors))
        for error in errors:
            self.log.error('report not rendered', error=error)
        return pages, errors

    def prune(self):
        """Delete old days and free space."""
        r = self.config.value.retention
        try:
            gone = prune(self.root, date.today(), r.days, r.min_free_gb)
        except OSError as error:
            self.log.error('reports not pruned', error=str(error))
            return
        if gone:
            self.log.warning('reports deleted', days=','.join(gone))
            self.builder().front()


def main(args=None):
    """Run report_node."""
    run(ReportNode, args=args, threads=2)


if __name__ == '__main__':
    main()
