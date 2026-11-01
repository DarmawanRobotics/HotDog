"""
The control mux as control_mux_node runs it (v0.2), and the v0.1 field rules (baseline).

MuxV02 drives dharma_control's Arbiter and Gate. MuxV01 keeps that arbitration and envelope
and replaces the field by the v0.1 rules: sector centres below range_max are obstacle points,
a point at the robot (a BLOCKED or zero range) is skipped, NaN sectors are free, a scan older
than 0.5 s (receive time) stops AUTO, and the field is off in REMOTE (the v0.1 default).
"""

from __future__ import annotations

import math

import numpy as np

from dharma_control.core.arbiter import Arbiter, Mode
from dharma_control.core.command import Command
from dharma_control.core.config import FieldConfig, MuxConfig
from dharma_control.core.envelope import Envelope
from dharma_control.core.gate import Gate
from dharma_control.core.scan import ScanData
from dharma_utils.robot import RobotProfile
from dharma_utils.safety import stopping_speed

V01_SCAN_TIMEOUT_SEC = 0.5
V01_MIN_SPEED = 0.02


class MuxV02:
    """Arbiter (mode, watchdog, re-arm) and Gate (envelope, protective field)."""

    def __init__(self, robot: RobotProfile, mode: str = 'auto', field: FieldConfig | None = None):
        self.config = MuxConfig(mode=mode)
        self.arbiter = Arbiter(self.config, 0.0)
        self.gate = Gate(robot, self.config, field or FieldConfig())
        self.base = robot.frames.base
        self.states: list[tuple[float, str]] = []

    @property
    def remote(self) -> bool:
        """True in REMOTE."""
        return self.arbiter.mode is Mode.REMOTE

    def forward(self, source: str, command, now: float):
        """Return the mux output for a command of source (None: nothing published)."""
        out = self.arbiter.on_command(source, Command(*command), now)
        if out is None:
            return None
        result = self.gate.apply(out, self.remote, now, now)
        self.states.append((now, result.field.value))
        c = result.command
        return (c.vx, c.vy, c.wz)

    def update_scan(self, scan, now: float):
        """Deliver a perception/safety_scan."""
        layout = scan.safety_layout
        data = ScanData(
            self.base, scan.stamp, layout.angle_min, layout.increment, layout.range_max,
            np.asarray(scan.safety, dtype=float),
        )  # fmt: skip
        self.gate.update_scan(data, now)

    def tick(self, now: float) -> bool:
        """Run the watchdog; True when one zero must be published."""
        return self.arbiter.tick(now)


class MuxV01(MuxV02):
    """Baseline: v0.2 arbitration and envelope, v0.1 protective field."""

    def __init__(self, robot: RobotProfile, mode: str = 'auto', field: FieldConfig | None = None):
        super().__init__(robot, mode, field)
        self.robot = robot
        self.envelope = Envelope(robot)
        self.points: list[tuple[float, float]] = []
        self.received: float | None = None

    def forward(self, source: str, command, now: float):
        """Return the mux output with the v0.1 field."""
        out = self.arbiter.on_command(source, Command(*command), now)
        if out is None:
            return None
        cmd = self.envelope.apply(out).command
        if self.remote:
            self.states.append((now, 'off'))
            return (cmd.vx, cmd.vy, cmd.wz)
        if self.received is None or now - self.received > V01_SCAN_TIMEOUT_SEC:
            self.states.append((now, 'stale'))
            return (0.0, 0.0, 0.0)
        scale = self.scale(cmd.vx, cmd.vy)
        self.states.append((now, 'clear' if scale >= 1.0 else 'limited'))
        return (cmd.vx * scale, cmd.vy * scale, cmd.wz)

    def update_scan(self, scan, now: float):
        """Keep the v0.1 obstacle points: sector centres with a range below range_max."""
        layout = scan.safety_layout
        theta = layout.angle_min + (np.arange(len(scan.safety)) + 0.5) * layout.increment
        r = np.asarray(scan.safety, dtype=float)
        hit = r < layout.range_max - 1e-3  # NaN compares False: free
        xs, ys = r[hit] * np.cos(theta[hit]), r[hit] * np.sin(theta[hit])
        self.points = list(zip(xs, ys))  # same mask: same length
        self.received = now

    def scale(self, vx: float, vy: float) -> float:
        """Return the v0.1 speed scale of a translation."""
        speed = math.hypot(vx, vy)
        if speed < V01_MIN_SPEED:
            return 1.0
        ux, uy = vx / speed, vy / speed
        room = self.clearance(ux, uy) - 0.15
        lim = self.robot.limits
        allowed = stopping_speed(room, lim.max_decel, lim.reaction_time)
        if allowed >= speed:
            return 1.0
        return 0.0 if allowed <= V01_MIN_SPEED else allowed / speed

    def clearance(self, ux: float, uy: float) -> float:
        """v0.1 path_clearance: points at or behind base_link along u are skipped."""
        fp = self.robot.footprint
        length = fp.front if ux >= 0.0 else fp.rear
        along_edge = abs(ux) * length + abs(uy) * fp.half_width
        half = abs(uy) * length + abs(ux) * fp.half_width
        clearance = math.inf
        for x, y in self.points:
            along, across = x * ux + y * uy, abs(-x * uy + y * ux)
            if along <= 0.0:
                continue
            if (along >= along_edge and across <= half + 0.10) or across <= half:
                clearance = min(clearance, along - along_edge)
        return clearance
