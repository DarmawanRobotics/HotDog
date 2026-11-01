"""
inspection_node: thermal and partial discharge inspection of the equipment at the stop points.

The path follower calls inspection/inspect (its hooks.inspection) at every stop point; the node
finds the site's inspection point nearest to where the robot stands, inspects its targets with
the UniPod MT11 (overheat analysis) and the Hertzinno HZ-FA-371 (partial discharge), writes the
report and answers. A stop with no point nearby answers at once, so it never holds the patrol.
inspection/add_target teaches a target from the pod's current pan, tilt and zoom.
"""

from __future__ import annotations

from datetime import datetime
import os
import threading
import time

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from std_srvs.srv import Trigger

from dharma_interfaces.msg import SiteStatus, StopPointEvent
from dharma_utils.ros import EVENTS, LATCHED, DharmaNode, run
from hotdog_inspection.core import plan as plans
from hotdog_inspection.core import report
from hotdog_inspection.core.config import InspectionConfig
from hotdog_inspection.core.discharge import AcousticCheck, Detector
from hotdog_inspection.core.hertzino import HertzinoClient, HertzinoError
from hotdog_inspection.core.runner import Runner
from hotdog_inspection.utils.convert import report_msg
from hotdog_inspection.utils.pod import PodClient
from hotdog_inspection.utils.teach import add_target_from_pod
from hotdog_interfaces.msg import Finding, InspectionReport, InspectionStatus
from hotdog_interfaces.srv import AddTarget

STATUS_PERIOD_SEC = 2.0
ACOUSTIC_PERIOD_SEC = 10.0  # how often the acoustic camera is asked whether it answers
WORKER_THREADS = 4  # the inspection blocks one thread while the pod answers on another
PASSWORD_ENV = 'HERTZINO_PASSWORD'
FACTORY_PASSWORD = '123456'


class InspectionNode(DharmaNode):
    """Inspects the site's inspection points when the follower stops there."""

    def __init__(self, **kwargs):
        super().__init__('inspection_node', **kwargs)
        self.config = self.declare_config(InspectionConfig)
        self.robot = self.declare_robot().value
        self.group = ReentrantCallbackGroup()
        self.busy = threading.Lock()
        self.closing = False
        self.site = ''
        self.stop = None  # (x, y, monotonic) of the stop the robot is at
        self.current, self.last = '', ('', 0)
        self.pod = PodClient(self, self.config.value.pod, self.group)
        self.acoustic_ok = False
        self.camera = self.acoustic_client()
        self.report_pub = self.create_publisher(InspectionReport, 'inspection/report', EVENTS)
        self.status_pub = self.latched(InspectionStatus, 'inspection/status')
        self.create_subscription(SiteStatus, 'site/status', self.on_site, LATCHED)
        self.create_subscription(StopPointEvent, 'navigation/stop_point', self.on_stop, EVENTS)
        self.create_service(Trigger, 'inspection/inspect', self.srv_inspect,
                            callback_group=self.group)  # fmt: skip
        self.create_service(AddTarget, 'inspection/add_target', self.srv_add_target,
                            callback_group=self.group)  # fmt: skip
        self.every(STATUS_PERIOD_SEC, self.publish_status)
        self.every(
            ACOUSTIC_PERIOD_SEC, self.check_acoustic, group=MutuallyExclusiveCallbackGroup()
        )
        self.add_shutdown_hook(self.on_shutdown)
        cfg = self.config.value
        self.log.info('inspection', enabled=cfg.enabled, pod=cfg.pod.namespace,
                      sites_dir=cfg.sites_dir)  # fmt: skip
        self.publish_status()

    def acoustic_client(self) -> HertzinoClient:
        """Return the acoustic camera's client (password from the environment, never a param)."""
        cfg = self.config.value.acoustic
        password = os.environ.get(PASSWORD_ENV, '')
        if not password:
            self.log.warning(f'{PASSWORD_ENV} unset: the factory password is used')
        return HertzinoClient(cfg.host, cfg.port, cfg.user, password or FACTORY_PASSWORD,
                              cfg.timeout_sec)  # fmt: skip

    def check_acoustic(self):
        """Ask the acoustic camera whether it answers (not while an inspection uses it)."""
        if self.current or not self.config.acoustic.enabled:
            return
        try:
            self.camera.detecting()
            self.acoustic_ok = True
        except HertzinoError as error:
            if self.acoustic_ok:
                self.log.warning('acoustic camera not answering', error=str(error))
            self.acoustic_ok = False

    # ---------------------------------------------------------------- inputs
    def on_site(self, msg: SiteStatus):
        """Follow the active site."""
        self.site = msg.site

    def on_stop(self, msg: StopPointEvent):
        """Remember where the robot stops; forget it when it leaves."""
        if msg.event == StopPointEvent.ARRIVED:
            self.stop = (msg.x, msg.y, time.monotonic())
        elif msg.event in (StopPointEvent.DEPARTED, StopPointEvent.SKIPPED):
            self.stop = None

    def robot_xy(self) -> tuple[float, float] | None:
        """Return where the robot stands: the stop it is at, else map -> base_link."""
        stop = self.stop
        if stop is not None and time.monotonic() - stop[2] < self.config.stop_max_age_sec:
            return stop[0], stop[1]
        result = self.tf.lookup(self.robot.frames.map, self.robot.frames.base)
        if result is None:
            return None
        pose = result.pose2d
        return pose.x, pose.y

    def plan(self) -> plans.Plan:
        """Return the plan of the active site (empty without a site)."""
        if not self.site:
            return plans.Plan()
        return plans.load(plans.plan_path(self.config.sites_dir, self.site))

    # ---------------------------------------------------------------- inspect
    def srv_inspect(self, _request, response):
        """Service (follower hook): inspect the point where the robot stands."""
        response.success, response.message = self.inspect()
        self.log.info('inspect', ok=response.success, detail=response.message)
        return response

    def inspect(self) -> tuple[bool, str]:
        """Run one inspection point; (ok, message)."""
        if not self.config.enabled:
            return True, 'inspection off'
        if not self.busy.acquire(blocking=False):
            return False, 'an inspection is running'
        try:
            return self.inspect_here()
        except plans.PlanError as error:
            self.log.error('inspection plan', error=str(error))
            return False, f'plan: {error}'
        finally:
            self.current = ''
            self.pod.end()
            self.busy.release()
            self.publish_status()

    def inspect_here(self) -> tuple[bool, str]:
        """Find the point here and inspect its targets."""
        here = self.robot_xy()
        if here is None:
            return False, 'robot pose unknown (not localized?)'
        point = self.plan().nearest(here[0], here[1], self.config.match_radius_m)
        if point is None:
            return True, f'no inspection point within {self.config.match_radius_m:.1f} m'
        self.current = point.name
        self.publish_status()
        when = datetime.now()
        directory = report.report_dir(self.config.reports_dir, when, point.name)
        self.pod.begin()
        cfg = self.config.value
        runner = Runner(cfg, self.pod)
        self.camera.timeout = cfg.acoustic.timeout_sec
        runner.checks.append(AcousticCheck(Detector(self.camera, cfg.acoustic), cfg.acoustic,
                                           cancelled=lambda: self.closing))  # fmt: skip
        result = runner.inspect(point, lambda t: report.evidence_prefix(directory, t.name),
                                cancelled=lambda: self.closing)  # fmt: skip
        report.write(directory, report.to_dict(result, self.site, here[0], here[1], when))
        msg = report_msg(result, self.site, here[0], here[1], directory,
                         self.get_clock().now().to_msg())  # fmt: skip
        self.report_pub.publish(msg)
        self.last = (point.name, msg.severity)
        if msg.severity >= Finding.WARNING:
            self.log.warning('finding', point=point.name, severity=report.severity_name(
                msg.severity), detail=result.message)  # fmt: skip
        return result.state != 'failed', result.message

    # ---------------------------------------------------------------- teach
    def srv_add_target(self, request, response):
        """Service: teach a target from the pod's pan, tilt and zoom where the robot stands."""
        ok, message, point, count = add_target_from_pod(self, request)
        response.success, response.message, response.point, response.targets = (
            ok, message, point, count)  # fmt: skip
        self.log.info('add_target', ok=ok, detail=message)
        self.publish_status()
        return response

    # ---------------------------------------------------------------- status
    def publish_status(self):
        """Publish inspection/status (latched)."""
        if self.closing:
            return
        msg = InspectionStatus(site=self.site, current=self.current)
        msg.header.stamp = self.get_clock().now().to_msg()
        if not self.config.enabled:
            msg.state = InspectionStatus.DISABLED
        elif self.current:
            msg.state = InspectionStatus.INSPECTING
        try:
            plan = self.plan()
            msg.points, msg.targets = len(plan.points), plan.targets
        except plans.PlanError as error:
            msg.message = f'plan: {error}'
        msg.pod_connected = self.pod.connected()
        msg.acoustic_connected = self.acoustic_ok
        msg.last_point, msg.last_severity = self.last
        msg.ambient_c = float(self.config.thermal.ambient_c)
        self.status_pub.publish(msg)

    def on_shutdown(self):
        """Stop a running inspection between two targets."""
        self.closing = True


def main(args=None):
    """Run inspection_node."""
    run(InspectionNode, args=args, threads=WORKER_THREADS)


if __name__ == '__main__':
    main()
