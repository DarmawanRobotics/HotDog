"""
The navigation side as path_follower_node and obstacle_avoidance_node run it, as a rig driver.

The follower core (dharma_navigation Follower) ticks at 20 Hz with the robot pose (the true
pose by default: localization is not part of E1, E2, E4 and E5), the 360 deg safety scan, the
measured twist, the mux state of control/status (e-stop, REMOTE, navigation armed) and the
output of the reactive avoidance policy on the front scan, which the bringup always runs (its
emergency stop holds the follower in every avoidance mode). The policy looks around the
direction of travel of navigation's last command (backward while reversing on a 360 deg scan),
as obstacle_avoidance_node does with control/nav_cmd_vel.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from common.rig import Rig
from dharma_navigation.core.avoidance import POLICIES
from dharma_navigation.core.avoidance.base import travel_direction
from dharma_navigation.core.config.avoidance import AvoidanceConfig
from dharma_navigation.core.config.follower import FollowerConfig
from dharma_navigation.core.controllers import CONTROLLERS, Command, ControllerLimits
from dharma_navigation.core.follower.fsm import Follower
from dharma_navigation.core.follower.state import FollowerState, Inputs, PoseInput, ScanInput
from dharma_navigation.core.path.route import Route
from dharma_navigation.core.scan import SectorScanData
from dharma_utils.math import Pose2D

POSE_AGE_SEC = 0.02
COMMAND_TIMEOUT_SEC = 0.5  # obstacle_avoidance_node: an older nav command is forward travel


def follower_config(**changes) -> FollowerConfig:
    """Return the package defaults (config/navigation.yaml has the same values) with changes."""
    return replace(FollowerConfig(), **changes)


class FollowerDriver:
    """Drives a rig with the follower; records the follower state of every tick."""

    def __init__(
        self,
        rig: Rig,
        points,
        config: FollowerConfig | None = None,
        start_sec: float = 1.0,
        pose: Callable[[Rig, float], Pose2D] | None = None,
    ):
        self.config = cfg = config or FollowerConfig()
        robot = rig.robot
        lim = robot.limits
        limits = ControllerLimits(lim.max_vx, lim.max_vy if robot.can_strafe else 0.0,
                                  lim.max_wz, 1.0 / cfg.control_rate)  # fmt: skip
        controller = CONTROLLERS.create(
            cfg.controller, CONTROLLERS.get(cfg.controller).Config(), limits
        )
        self.follower = Follower(cfg, robot, controller)
        self.follower.set_route(Route.from_points(points))
        self.follower.on_localization(True)
        avoidance = AvoidanceConfig()
        self.policy = POLICIES.create(
            avoidance.policy, avoidance.shared, avoidance.policy_config(), robot=robot
        )
        self.start_sec = start_sec
        self.pose = pose or (lambda r, now: r.pose)
        self.started = False
        self.scan = None
        self.avoidance = None
        self.last_command = (0.0, -float('inf'))  # vx of control/nav_cmd_vel, time
        self.states: list[tuple[float, FollowerState]] = []
        rig.listeners.append(self.on_scan)

    def on_scan(self, scan, now: float):
        """Keep the safety scan (edge points, sector centres, blocked); run the avoidance."""
        s = scan.safety_layout
        data = SectorScanData.of(s.angle_min, s.increment, s.range_max, scan.safety)
        sectors, centres = data.points(), data.points(edges=False)  # path shift, guard
        self.scan = (sectors.points, centres.points, sectors.any_blocked, now)
        f = scan.front_layout
        front = SectorScanData.of(f.angle_min, f.increment, f.range_max, scan.front)
        vx, at = self.last_command
        vx = vx if now - at <= COMMAND_TIMEOUT_SEC else 0.0
        direction = travel_direction(vx, front.points(edges=False).full_circle)
        self.avoidance = (self.policy.update(front, direction), now)

    def __call__(self, rig: Rig, now: float):
        """Run one control tick; return the command to publish (None: nothing)."""
        if now < self.start_sec:
            return None
        pose = self.pose(rig, now)
        arbiter = rig.mux.arbiter  # control/status
        self.follower.on_control(arbiter.engaged, rig.mux.remote, arbiter.armed)
        if not self.started:
            ok, _ = self.follower.start(pose)
            self.started = ok
        scan = avoidance = None
        age = float('inf')
        if self.scan is not None:
            points, centres, blocked, at = self.scan
            scan = ScanInput(points, blocked, now - at, centres)
        if self.avoidance is not None:
            avoidance, at = self.avoidance
            age = now - at
        t = rig.sim.body.twist
        dt = 1.0 / self.config.control_rate
        inputs = Inputs(now, dt, PoseInput(pose, POSE_AGE_SEC), scan, avoidance, age,
                        Command(t.vx, t.vy, t.wz))  # fmt: skip
        decision = self.follower.tick(inputs)
        self.states.append((now, decision.report.state))
        c = decision.command
        if c is None:
            return None
        self.last_command = (c.vx, now)
        return (c.vx, c.vy, c.wz)

    @property
    def state(self) -> FollowerState:
        """Return the reported state."""
        return self.follower.state
