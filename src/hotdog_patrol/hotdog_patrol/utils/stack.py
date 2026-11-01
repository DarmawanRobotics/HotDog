"""The services patrol_node drives: localization, the control mux, the follower, the M20."""

from __future__ import annotations

from hotdog_base.utils.calls import call
from std_srvs.srv import Trigger

from dharma_interfaces.srv import LoadPath, SetMode
from hotdog_patrol.core.config import PatrolConfig, with_ns


class StackClients:
    """Blocking calls (worker threads only) returning (ok, message)."""

    def __init__(self, node, config: PatrolConfig, group):
        def client(srv, name):
            name = with_ns(name, config.robot_ns)
            return node.create_client(srv, name, callback_group=group) if name else None

        self.timeout = config.start.call_timeout_sec
        self.assume_origin = client(Trigger, 'localization/assume_origin')
        self.set_mode = client(SetMode, 'control/set_mode')
        self.load_path = client(LoadPath, 'navigation/load_path')
        self.nav_start = client(Trigger, 'navigation/start')
        self.nav_stop = client(Trigger, 'navigation/stop')
        self.stand_up = client(Trigger, config.start.stand_up_service)
        self.dock = client(Trigger, config.finish.dock_service)

    def trigger(self, client, timeout: float = 0.0) -> tuple[bool, str]:
        """Call a Trigger service."""
        res, error = call(client, Trigger.Request(), timeout or self.timeout)
        return (res.success, res.message) if res is not None else (False, error)

    def auto(self) -> tuple[bool, str]:
        """Let navigation drive (control/set_mode auto)."""
        res, error = call(self.set_mode, SetMode.Request(mode='auto'), self.timeout)
        return (res.success, res.message) if res is not None else (False, error)

    def load(self, path: str) -> tuple[bool, str]:
        """Load a route (relative to sites_dir) into the follower."""
        res, error = call(self.load_path, LoadPath.Request(path=path), self.timeout)
        return (res.success, res.message) if res is not None else (False, error)

    def dock_robot(self, log):
        """Send the M20 to its dock (charge_start) and log the answer."""
        ok, message = self.trigger(self.dock)
        (log.info if ok else log.error)('dock', ok=ok, detail=message)

    def stop_async(self):
        """Stop the follower without waiting (from a callback)."""
        self.nav_stop.call_async(Trigger.Request())
