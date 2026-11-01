"""
patrol_node: route patrols from the dock, on demand or at fixed times of the day.

patrol/start runs the start sequence in a worker thread (health, e-stop and battery checks,
localization/assume_origin at the dock, the robot's stand-up, AUTO mode, the route, the
follower's start), then follows navigation/status to the end of the route, counts the
inspection reports on the way, writes the patrol summary and sends the M20 back to its dock.
"""

from __future__ import annotations

from datetime import datetime
import os
import threading
import time

from hotdog_base.utils.calls import call
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from sensor_msgs.msg import BatteryState
from std_srvs.srv import Trigger

from dharma_interfaces.msg import ControlStatus, HealthStatus, NavigationStatus, SiteStatus
from dharma_interfaces.srv import LoadPath, SetMode
from dharma_utils.io import expand, write_json_atomic
from dharma_utils.ros import EVENTS, LATCHED, SENSOR, DharmaNode, run
from hotdog_interfaces.msg import InspectionReport, PatrolStatus
from hotdog_interfaces.srv import StartPatrol
from hotdog_patrol.core.config import PatrolConfig, with_ns
from hotdog_patrol.core.schedule import ScheduleError, due, next_slot
from hotdog_patrol.core.session import Session, State, route_path, run_steps

STATUS_PERIOD_SEC = 2.0
SCHEDULE_PERIOD_SEC = 10.0


class PatrolNode(DharmaNode):
    """Starts, follows and reports route patrols."""

    def __init__(self, **kwargs):
        super().__init__('patrol_node', **kwargs)
        self.config = self.declare_config(PatrolConfig)
        self.group = ReentrantCallbackGroup()
        self.lock = threading.Lock()
        self.session = Session()
        self.fired: set = set()  # schedule slots already started or skipped
        self.site, self.health, self.control, self.battery = '', None, None, None
        self.status_pub = self.latched(PatrolStatus, 'patrol/status')
        sub = self.create_subscription
        sub(SiteStatus, 'site/status', lambda m: setattr(self, 'site', m.site), LATCHED)
        sub(HealthStatus, 'health/status', lambda m: setattr(self, 'health', m), LATCHED)
        sub(ControlStatus, 'control/status', lambda m: setattr(self, 'control', m), LATCHED)
        cfg = self.config.value
        sub(BatteryState, with_ns(cfg.battery_topic, cfg.robot_ns), self.on_battery, SENSOR)
        sub(NavigationStatus, 'navigation/status', self.on_navigation, LATCHED)
        sub(InspectionReport, 'inspection/report', self.on_report, EVENTS)

        def client(srv, name):
            name = with_ns(name, cfg.robot_ns)
            return self.create_client(srv, name, callback_group=self.group) if name else None

        self.assume_origin = client(Trigger, 'localization/assume_origin')
        self.set_mode = client(SetMode, 'control/set_mode')
        self.load_path = client(LoadPath, 'navigation/load_path')
        self.nav_start = client(Trigger, 'navigation/start')
        self.nav_stop = client(Trigger, 'navigation/stop')
        self.stand_up = client(Trigger, cfg.start.stand_up_service)
        self.dock = client(Trigger, cfg.finish.dock_service)
        self.create_service(StartPatrol, 'patrol/start', self.srv_start, callback_group=self.group)
        self.create_service(Trigger, 'patrol/stop', self.srv_stop, callback_group=self.group)
        self.every(STATUS_PERIOD_SEC, self.publish_status)
        group = MutuallyExclusiveCallbackGroup()
        self.every(SCHEDULE_PERIOD_SEC, self.check_schedule, group=group)
        self.log.info('patrol', schedule=cfg.schedule.enabled, times=','.join(cfg.schedule.times))
        self.publish_status()

    # ---------------------------------------------------------------- inputs
    def on_battery(self, msg: BatteryState):
        """Keep the battery fraction."""
        self.battery = float(msg.percentage)

    def on_navigation(self, msg: NavigationStatus):
        """Follow the follower to the end of the route."""
        with self.lock:
            ended = self.session.on_navigation(msg.state, msg.message)
        if ended:
            self.finish()

    def on_report(self, msg: InspectionReport):
        """Count an inspected point of the running patrol."""
        with self.lock:
            self.session.on_report([f.severity for f in msg.findings])

    # ---------------------------------------------------------------- start
    def srv_start(self, request, response):
        """Service: start a patrol (answers once the start sequence runs)."""
        response.success, response.message = self.start(request.route)
        self.log.info('patrol/start', ok=response.success, detail=response.message)
        return response

    def start(self, route: str) -> tuple[bool, str]:
        """Begin the start sequence of a patrol in a worker thread."""
        with self.lock:
            if self.session.busy:
                return False, f'a patrol is {self.session.state.name.lower()}'
            if not self.site:
                return False, 'no site loaded (site/load)'
            try:
                path = route_path(self.site, route)
            except ValueError as error:
                return False, str(error)
            self.session = Session(route=path, site=self.site, started=time.time(),
                                   state=State.STARTING, message='starting')  # fmt: skip
        threading.Thread(target=self.run_start, args=(path,), daemon=True).start()
        self.publish_status()
        return True, f'starting {path or "the route loaded last"}'

    def run_start(self, path: str):
        """Run the start steps; RUNNING when every one succeeded, else FAILED."""
        cfg = self.config.value.start
        steps = [('checks', self.checks)]
        if cfg.reanchor:
            steps.append(('re-anchor', lambda: self.trigger(self.assume_origin)))
        if self.stand_up is not None:
            timeout = cfg.stand_up_timeout_sec
            steps.append(('stand up', lambda: self.trigger(self.stand_up, timeout)))
        steps.append(('auto', self.auto_mode))
        if path:
            steps.append(('route', lambda: self.load(path)))
        steps.append(('start', lambda: self.trigger(self.nav_start)))
        ok, message = run_steps(steps)
        with self.lock:
            if self.session.state is State.STARTING:
                self.session.state = State.RUNNING if ok else State.FAILED
                self.session.message = message
        if not ok:
            self.log.error('patrol not started', detail=message)
            self.finish()
        self.publish_status()

    def checks(self) -> tuple[bool, str]:
        """Return whether the robot may start: health, e-stop, battery."""
        cfg = self.config.value.start
        health, control, battery = self.health, self.control, self.battery
        if health is not None and health.level > cfg.max_health:
            return False, f'health level {health.level}: {"; ".join(health.issues)}'
        if control is not None and control.estop:
            return False, 'the e-stop is engaged'
        if cfg.min_battery > 0.0 and (battery is None or battery < cfg.min_battery):
            return False, f'battery {battery if battery is not None else "unknown"}'
        return True, 'ok'

    def trigger(self, client, timeout: float = 0.0) -> tuple[bool, str]:
        """Call a Trigger service; (ok, message)."""
        timeout = timeout or self.config.start.call_timeout_sec
        res, error = call(client, Trigger.Request(), timeout)
        return (res.success, res.message) if res is not None else (False, error)

    def auto_mode(self) -> tuple[bool, str]:
        """Let navigation drive (control/set_mode auto)."""
        res, error = call(self.set_mode, SetMode.Request(mode='auto'),
                          self.config.start.call_timeout_sec)  # fmt: skip
        return (res.success, res.message) if res is not None else (False, error)

    def load(self, path: str) -> tuple[bool, str]:
        """Load the route into the follower."""
        res, error = call(self.load_path, LoadPath.Request(path=path),
                          self.config.start.call_timeout_sec)  # fmt: skip
        return (res.success, res.message) if res is not None else (False, error)

    # ---------------------------------------------------------------- end
    def srv_stop(self, _request, response):
        """Service: stop the patrol (the follower stops, the robot stands)."""
        with self.lock:
            ended = self.session.end(State.STOPPED, 'stopped by patrol/stop')
        if ended:
            self.nav_stop.call_async(Trigger.Request())
            self.finish()
        response.success = ended
        response.message = 'stopped' if ended else 'no patrol running'
        return response

    def finish(self):
        """Write the patrol summary; after a finished route send the robot to its dock."""
        with self.lock:
            session = self.session
            summary = session.summary(time.time())
        when = datetime.fromtimestamp(session.started or time.time())
        path = os.path.join(expand(self.config.reports_dir), when.strftime('%Y%m%d'),
                            f'patrol_{when.strftime("%H%M%S")}.json')  # fmt: skip
        try:
            write_json_atomic(path, summary, backup=False)
            session.report = path
        except OSError as error:
            self.log.error('patrol summary not written', error=str(error))
        self.log.info('patrol ended', state=summary['state'], points=summary['points'],
                      worst=summary['worst'], detail=summary['message'])  # fmt: skip
        if session.state is State.DONE and self.dock is not None:
            threading.Thread(target=lambda: self.log.info(
                'dock', result=str(self.trigger(self.dock))), daemon=True).start()  # fmt: skip
        self.publish_status()

    # ---------------------------------------------------------------- schedule
    def check_schedule(self):
        """Start the patrol of a due slot (a slot due while busy is skipped)."""
        cfg = self.config.value.schedule
        if not cfg.enabled:
            return
        try:
            slot = due(datetime.now(), cfg.times, cfg.window_min, self.fired)
        except ScheduleError as error:
            self.log.error('schedule', error=str(error), throttle=60.0)
            return
        if slot is None:
            return
        self.fired.add(slot)
        ok, message = self.start(cfg.route)
        self.log.info('scheduled patrol', slot=slot.strftime('%H:%M'), ok=ok, detail=message)

    # ---------------------------------------------------------------- status
    def publish_status(self):
        """Publish patrol/status (latched)."""
        cfg = self.config.value.schedule
        with self.lock:
            s = self.session
            msg = PatrolStatus(state=int(s.state), site=s.site, route=s.route, started=s.started,
                               points=s.points, worst=s.worst, report=s.report,
                               message=s.message)  # fmt: skip
            msg.attention, msg.warning, msg.critical = (
                s.counts['attention'], s.counts['warning'], s.counts['critical'])  # fmt: skip
            msg.elapsed_sec = float(time.time() - s.started) if s.busy else 0.0
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.schedule_enabled = cfg.enabled
        try:
            nxt = next_slot(datetime.now(), cfg.times) if cfg.enabled else None
        except ScheduleError:
            nxt = None
        msg.next_scheduled = nxt.strftime('%H:%M') if nxt else ''
        self.status_pub.publish(msg)


def main(args=None):
    """Run patrol_node."""
    run(PatrolNode, args=args, threads=4)


if __name__ == '__main__':
    main()
