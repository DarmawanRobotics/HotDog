"""The way back to the dock along the taught route, and the remembered route (no ROS)."""

from __future__ import annotations

import math

from hotdog_patrol.core import retreat

from dharma_utils.io import RoutePoint


def line(n: int, step: float = 1.0) -> list[RoutePoint]:
    """A straight route along x from the dock at the origin, a stop point in the middle."""
    return [RoutePoint(i * step, 0.0, 0.0, 5.0 if i == n // 2 else 0.0) for i in range(n)]


def out_and_back() -> list[RoutePoint]:
    """Out along x to 10 m and back along the same walkway (0.2 m to the side)."""
    out = [RoutePoint(float(i), 0.0, 0.0) for i in range(11)]
    back = [RoutePoint(float(i), 0.2, math.pi) for i in range(9, -1, -1)]
    return out + back


def test_back_along_the_route_facing_the_way():
    way = retreat.return_route(line(11), 6.1, 0.3, near_m=0.5, clearance_m=1.0)
    assert [p.x for p in way] == [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    assert all(p.dwell_sec == 0.0 for p in way)  # no stop points on the way back
    assert all(abs(abs(p.yaw) - math.pi) < 1e-9 for p in way)  # facing the dock


def test_the_earliest_near_waypoint_is_the_short_way():
    route = out_and_back()
    way = retreat.return_route(route, 3.0, 0.1, near_m=0.5, clearance_m=1.0)
    assert [p.x for p in way] == [3.0, 2.0, 1.0]  # not around the far end


def test_the_nearest_point_of_the_first_pass_with_a_wide_near():
    way = retreat.return_route(line(11), 6.0, 0.0, near_m=2.0, clearance_m=1.0)
    assert way[0].x == 6.0  # not 4.0, the earliest one within 2 m
    route = out_and_back()
    assert retreat.return_route(route, 3.0, 0.1, near_m=2.0, clearance_m=1.0)[0].x == 3.0


def test_far_from_the_route_starts_at_the_nearest_point():
    way = retreat.return_route(line(11), 8.0, 5.0, near_m=0.5, clearance_m=0.0)
    assert way[0].x == 8.0 and way[-1].x == 0.0


def test_at_the_dock_already():
    assert retreat.return_route(line(11), 0.5, 0.0, near_m=0.6, clearance_m=1.0) == []
    assert retreat.return_route(line(3, 0.2), 0.4, 0.0, near_m=0.5, clearance_m=1.0) == []
    assert retreat.return_route([], 1.0, 1.0, near_m=1.0, clearance_m=1.0) == []


def test_the_last_route_is_remembered_per_site(tmp_path):
    sites = str(tmp_path)
    assert retreat.remembered_route(sites, 'gi') == ''
    retreat.remember_route(sites, 'gi', 'gi/routes/r1.csv')
    assert retreat.remembered_route(sites, 'gi') == 'gi/routes/r1.csv'
    assert retreat.remembered_route(sites, 'other') == ''
    (tmp_path / 'gi' / 'patrol' / 'state.json').write_text('{"last_route": "../../etc/x"}')
    assert retreat.remembered_route(sites, 'gi') == ''  # only a route of the site
    (tmp_path / 'gi' / 'patrol' / 'state.json').write_text('not json')
    assert retreat.remembered_route(sites, 'gi') == ''
    assert retreat.return_relative('gi') == 'gi/patrol/return.csv'
