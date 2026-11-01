"""The way back to the dock from the robot's pose: written as a route the follower can load."""

from __future__ import annotations

import os
import time

from dharma_utils.io import PathError, RouteError, expand, read_route, resolve_inside, write_route
from hotdog_patrol.core import retreat


class ReturnPlanner:
    """Plans the return of patrol_node (worker threads only: it waits for TF)."""

    def __init__(self, node):
        self.node = node

    def plan(self, site: str, route: str) -> tuple[bool, str]:
        """Return (True, route to load), (True, '') at the dock already, or (False, error)."""
        cfg = self.node.config.value
        if not route:
            return False, 'the route is unknown (started with the route loaded last)'
        sites_dir = expand(cfg.sites_dir)
        try:
            points = read_route(resolve_inside(sites_dir, route))
        except (PathError, RouteError) as error:
            return False, str(error)
        pose = self.pose(cfg.abort.pose_timeout_sec)
        if pose is None:
            return False, 'no map -> base pose'
        a = cfg.abort
        way = retreat.return_route(points, pose.x, pose.y, a.near_m, a.dock_clearance_m)
        if not way:
            return True, ''
        path = os.path.join(retreat.patrol_dir(sites_dir, site), retreat.RETURN_FILE)
        try:
            write_route(path, way)
        except OSError as error:
            return False, f'{path}: {error}'
        self.node.log.info('way back', points=len(way), x=round(pose.x, 2), y=round(pose.y, 2))
        return True, retreat.return_relative(site)

    def remember(self, site: str, route: str):
        """Keep the route for the next patrol started without one."""
        try:
            retreat.remember_route(expand(self.node.config.sites_dir), site, route)
        except OSError as error:
            self.node.log.warning('last route not kept', error=str(error))

    def pose(self, timeout: float):
        """Return the robot's map pose (Pose2D) or None after timeout."""
        frames = self.node.robot.frames
        deadline = time.monotonic() + timeout
        while True:
            result = self.node.tf.lookup(frames.map, frames.base)
            if result is not None:
                return result.pose2d()
            if time.monotonic() > deadline:
                return None
            time.sleep(0.1)
