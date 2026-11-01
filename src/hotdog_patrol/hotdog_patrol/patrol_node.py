"""
patrol_node: route patrols from the dock, on demand or at fixed times of the day.

patrol/start runs the start sequence in a worker thread (health, e-stop and battery checks,
localization/assume_origin at the dock, the robot's stand-up, AUTO mode, the route, the
follower's start), then follows navigation/status to the end of the route, counts the
inspection reports on the way, writes the patrol summary and sends the M20 back to its dock.
A watchdog walks the taught route back to the dock on a low battery, an overlong patrol or a
blocked robot (patrol/return does the same on request), and stops a lost or silent patrol.
"""

from __future__ import annotations

from datetime import datetime
import os
import threading
import time

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from sensor_msgs.msg import BatteryState
from std_srvs.srv import Trigger

from dharma_interfaces.msg import ControlStatus, HealthStatus, NavigationStatus, SiteStatus
from dharma_utils.io import expand, write_json_atomic
from dharma_utils.ros import EVENTS, LATCHED, SENSOR, DharmaNode, run
from hotdog_interfaces.msg import InspectionReport, PatrolStatus
from hotdog_interfaces.srv import StartPatrol
from hotdog_patrol.core import retreat
from hotdog_patrol.core.config import PatrolConfig, with_ns
from hotdog_patrol.core.schedule import ScheduleError, due
from hotdog_patrol.core.session import Session, State, route_path, run_steps, start_checks
from hotdog_patrol.core.watchdog import RETURN, Watchdog
from hotdog_patrol.utils.returning import ReturnPlanner
from hotdog_patrol.utils.stack import StackClients
from hotdog_patrol.utils.status import status_msg

STATUS_PERIOD_SEC = 2.0
SCHEDULE_PERIOD_SEC = 10.0
WATCHDOG_PERIOD_SEC = 1.0


class PatrolNode(DharmaNode):
    """Starts, follows, guards and reports route patrols."""

    def __init__(self, **kwargs):
        super().__init__('patrol_node', **kwargs)
        self.config = self.declare_config(PatrolConfig)
        self.robot = self.declare_robot().value
        self.group = ReentrantCallbackGroup()
        self.lock = threading.Lock()
        self.session = Session()
        self.watchdog = Watchdog(self.config.value.abort)
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
        self.stack = StackClients(self, cfg, self.group)
        self.planner = ReturnPlanner(self)
        srv = self.create_service
        srv(StartPatrol, 'patrol/start', self.srv_start, callback_group=self.group)
        srv(Trigger, 'patrol/stop', self.srv_stop, callback_group=self.group)
        srv(Trigger, 'patrol/return', self.srv_return, callback_group=self.group)
        self.every(STATUS_PERIOD_SEC, self.publish_status)
        self.every(
            SCHEDULE_PERIOD_SEC, self.check_schedule, group=MutuallyExclusiveCallbackGroup()
        )
        self.every(WATCHDOG_PERIOD_SEC, self.guard, group=MutuallyExclusiveCallbackGroup())
        self.log.info('patrol', schedule=cfg.schedule.enabled, times=','.join(cfg.schedule.times))
        self.publish_status()

    # ---------------------------------------------------------------- inputs
    def on_battery(self, msg: BatteryState):
        """Keep the battery fraction."""
        self.battery = float(msg.percentage)

    def on_navigation(self, msg: NavigationStatus):
        """Follow the follower to the end of the route (or back to the dock)."""
        with self.lock:
            self.watchdog.on_navigation(msg.state, msg.pause_reasons, time.monotonic())
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            ended = self.session.on_navigation(msg.state, msg.message, stamp)
        if ended:
            self.finish()

    def on_report(self, msg: InspectionReport):
        """Count an inspected point of the running patrol."""
        with self.lock:
            self.session.on_report([f.severity for f in msg.findings], msg.directory)

    # ---------------------------------------------------------------- start
    def srv_start(self, request, response):
        """Service: start a patrol (answers once the start sequence runs)."""
        response.success, response.message = self.start(request.route)
        self.log.info('patrol/start', ok=response.success, detail=response.message)
        return response

    def start(self, route: str) -> tuple[bool, str]:
        """Begin the start sequence of a patrol in a worker thread."""
        sites_dir = expand(self.config.sites_dir)
        with self.lock:
            if self.session.busy:
                return False, f'a patrol is {self.session.state.name.lower()}'
            if not self.site:
                return False, 'no site loaded (site/load)'
            try:
                path = route_path(self.site, route) or retreat.remembered_route(
                    sites_dir, self.site
                )
            except ValueError as error:
                return False, str(error)
            self.session = Session(route=path, site=self.site, started=time.time(),
                                   state=State.STARTING, message='starting')  # fmt: skip
        threading.Thread(target=self.run_start, args=(path,), daemon=True).start()
        self.publish_status()
        return True, f'starting {path or "the route loaded last"}'

    def run_start(self, path: str):
        """Run the start steps; RUNNING when every one succeeded, else FAILED."""
        cfg, stack = self.config.value.start, self.stack
        steps = [('checks', self.checks)]
        if cfg.reanchor:
            steps.append(('re-anchor', lambda: stack.trigger(stack.assume_origin)))
        if stack.stand_up is not None:
            timeout = cfg.stand_up_timeout_sec
            steps.append(('stand up', lambda: stack.trigger(stack.stand_up, timeout)))
        steps.append(('auto', stack.auto))
        if path:
            steps.append(('route', lambda: stack.load(path)))
        steps.append(('start', lambda: stack.trigger(stack.nav_start)))
        ok, message = run_steps(steps)
        with self.lock:
            if self.session.state is State.STARTING:
                self.session.state = State.RUNNING if ok else State.FAILED
                self.session.message = message
                self.watchdog.reset(time.monotonic())
        if ok and path:
            self.planner.remember(self.site, path)
        if not ok:
            self.log.error('patrol not started', detail=message)
            self.finish()
        self.publish_status()

    def checks(self) -> tuple[bool, str]:
        """Return whether the robot may start: health, e-stop, battery."""
        return start_checks(self.config.value.start, self.health, self.control, self.battery)

    # ---------------------------------------------------------------- watchdog
    def guard(self):
        """Check the running patrol or its way back."""
        with self.lock:
            state = self.session.state
            if state not in (State.RUNNING, State.RETURNING):
                return
            verdict = self.watchdog.check(
                time.monotonic(), self.battery, returning=state is State.RETURNING
            )
        if not verdict.action:
            return
        self.log.warning('patrol watchdog', action=verdict.action, reason=verdict.reason)
        if verdict.action == RETURN and self.config.value.abort.return_to_dock:
            self.begin_return(State.FAILED, verdict.reason)
        else:
            self.abort(verdict.reason)

    def abort(self, reason: str):
        """Fail the patrol where the robot stands."""
        with self.lock:
            ended = self.session.end(State.FAILED, reason)
        if ended:
            self.stack.stop_async()
            self.finish()

    def srv_return(self, _request, response):
        """Service: walk the route back to the dock now."""
        response.success, response.message = self.begin_return(State.STOPPED, 'operator')
        return response

    def begin_return(self, final: State, reason: str) -> tuple[bool, str]:
        """Turn the running patrol into its way back to the dock."""
        with self.lock:
            if not self.session.begin_return(final, reason):
                return False, f'no patrol running ({self.session.state.name.lower()})'
            self.watchdog.reset(time.monotonic())
            session = self.session
        self.log.warning('returning to the dock', reason=reason)
        threading.Thread(target=self.run_return, args=(session,), daemon=True).start()
        self.publish_status()
        return True, f'returning to the dock: {reason}'

    def run_return(self, session: Session):
        """Stop the follower, plan the way back along the route, follow it."""
        stack = self.stack
        stack.trigger(stack.nav_stop)
        ok, detail = self.planner.plan(session.site, session.route)
        if ok and detail:
            steps = [('auto', stack.auto), ('load', lambda: stack.load(detail)),
                     ('start', self.start_return)]  # fmt: skip
            ok, detail = run_steps(steps)
            if ok:
                self.publish_status()
                return
        with self.lock:
            if session is not self.session:
                return
            if ok:  # within dock_clearance_m of the dock already
                ended = session.end(session.final, f'at the dock: {session.reason}')
                session.returned = ended
            else:
                ended = session.end(State.FAILED, f'no way back ({session.reason}): {detail}')
        if ended:
            self.finish()

    def start_return(self) -> tuple[bool, str]:
        """Start the follower on the way back; only its statuses from now on count."""
        with self.lock:
            if self.session.state is not State.RETURNING:
                return False, 'the way back was stopped'
            self.session.ignore_before = self.get_clock().now().nanoseconds * 1e-9
        return self.stack.trigger(self.stack.nav_start)

    # ---------------------------------------------------------------- end
    def srv_stop(self, _request, response):
        """Service: stop the patrol or its way back (the follower stops, the robot stands)."""
        with self.lock:
            ended = self.session.end(State.STOPPED, 'stopped by patrol/stop')
        if ended:
            self.stack.stop_async()
            self.finish()
        response.success = ended
        response.message = 'stopped' if ended else 'no patrol running'
        return response

    def finish(self):
        """Write the patrol summary; at the end of the route or back home, dock the M20."""
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
        if (session.state is State.DONE or session.returned) and self.stack.dock is not None:
            threading.Thread(target=self.dock, daemon=True).start()
        self.publish_status()

    def dock(self):
        """Send the M20 to its dock (charge_start)."""
        ok, message = self.stack.trigger(self.stack.dock)
        (self.log.info if ok else self.log.error)('dock', ok=ok, detail=message)

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
        with self.lock:
            msg = status_msg(self.session, self.battery, self.config.value.schedule)
        msg.header.stamp = self.get_clock().now().to_msg()
        self.status_pub.publish(msg)


def main(args=None):
    """Run patrol_node."""
    run(PatrolNode, args=args, threads=4)


if __name__ == '__main__':
    main()
