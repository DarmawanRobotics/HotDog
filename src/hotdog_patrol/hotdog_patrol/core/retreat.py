"""
The way back to the dock: the taught route walked backwards from where the robot stands.

Odometry only, nothing is mapped, so the only ground known to be clear is the taught route.
The return starts at the earliest waypoint near the robot (a route out and back along the same
walkway returns the short way), runs back towards the route's start (the dock, where every
route is taught from) without stop points, and ends dock_clearance_m before it: the M20 docks
itself from there (charge_start).
"""

from __future__ import annotations

import math
import os

from dharma_utils.io import RoutePoint, read_json, write_json_atomic

RETURN_FILE = 'return.csv'  # <site>/patrol/return.csv, rewritten at every return
STATE_FILE = 'state.json'  # <site>/patrol/state.json: the last route patrolled


def start_index(points: list[RoutePoint], x: float, y: float, near_m: float) -> int:
    """Return the earliest waypoint within near_m of (x, y), else the nearest one."""
    distances = [math.hypot(p.x - x, p.y - y) for p in points]
    for i, d in enumerate(distances):
        if d <= near_m:
            return i
    return min(range(len(points)), key=distances.__getitem__)


def first_beyond(points: list[RoutePoint], distance: float):
    """Return the index of the first waypoint distance or more from the first one, or None."""
    o = points[0]
    far = (i for i, p in enumerate(points) if math.hypot(p.x - o.x, p.y - o.y) >= distance)
    return next(far, None)


def return_route(
    points: list[RoutePoint], x: float, y: float, near_m: float, clearance_m: float
) -> list[RoutePoint]:
    """Return the route back to the dock from (x, y); [] when the robot is at the dock already.

    Waypoints face the direction of travel (the robot walks forward on the way back) and none
    is a stop point. The last one is the first waypoint of the route clearance_m or more away
    from its start.
    """
    if not points:
        return []
    end = first_beyond(points, clearance_m)
    if end is None:
        return []
    first = start_index(points, x, y, near_m)
    if first <= end:
        return []
    way = points[end : first + 1][::-1]
    out = []
    for i, p in enumerate(way):
        a, b = (p, way[i + 1]) if i + 1 < len(way) else (way[i - 1], p)
        yaw = math.atan2(b.y - a.y, b.x - a.x)
        out.append(RoutePoint(p.x, p.y, yaw, 0.0))
    return out


def patrol_dir(sites_dir: str, site: str) -> str:
    """Return <sites_dir>/<site>/patrol."""
    return os.path.join(sites_dir, site, 'patrol')


def return_relative(site: str) -> str:
    """Return the return route relative to sites_dir (navigation/load_path)."""
    return f'{site}/patrol/{RETURN_FILE}'


def remembered_route(sites_dir: str, site: str) -> str:
    """Return the last route patrolled on the site (relative to sites_dir), '' when none."""
    data, _error = read_json(os.path.join(patrol_dir(sites_dir, site), STATE_FILE))
    route = data.get('last_route', '') if isinstance(data, dict) else ''
    expected = f'{site}/routes/'
    return route if isinstance(route, str) and route.startswith(expected) else ''


def remember_route(sites_dir: str, site: str, route: str):
    """Keep the route patrolled (raise OSError)."""
    path = os.path.join(patrol_dir(sites_dir, site), STATE_FILE)
    write_json_atomic(path, {'last_route': route}, backup=False)
