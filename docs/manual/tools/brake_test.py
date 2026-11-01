"""
Measure the braking limits of a robot: reaction time and deceleration from step-to-zero runs.

    brake_test.py drive --speed 0.5 --out run1.csv      # on the robot (rclpy), through the mux
    brake_test.py analyze run1.csv run2.csv ...         # anywhere (numpy only)
    brake_test.py demo --out demo.csv                   # a run of the dharma_sim body model

drive switches nothing: put the mux in REMOTE with the source first (control/set_mode). It sends
zeros (re-arm), then the speed for --hold seconds, then zeros, on control/remote/<source>/cmd_vel
at 50 Hz, and records the measured speed of an Odometry topic. Every CSV has the columns t (s),
cmd and v (m/s, or rad/s with --axis angular; nan on the rows that only mark a command change).
analyze fits the deceleration between 80 % and 20 % of the speed before the step; the reaction
time is from the step command to where that line meets the speed before the step (it includes
the mux, transport, the driver and the odometry).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import sys

import numpy as np

RATE_HZ = 50.0
STEADY_SEC = 0.5  # speed before the step: mean over this window
EPS = 1e-3


@dataclass(frozen=True)
class Brake:
    """One run: speed before the step, reaction, deceleration, measured and model distance."""

    v0: float
    reaction_sec: float
    decel: float
    distance: float
    model_distance: float


def read_run(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return t, cmd, v of a CSV run."""
    with path.open(newline='', encoding='utf-8') as f:
        rows = [(float(r['t']), float(r['cmd']), float(r['v'])) for r in csv.DictReader(f)]
    data = np.array(rows, dtype=float).reshape(-1, 3)
    return data[:, 0], data[:, 1], data[:, 2]


def write_run(path: Path, rows) -> None:
    """Write (t, cmd, v) rows."""
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['t', 'cmd', 'v'])
        writer.writerows((f'{t:.4f}', f'{c:.4f}', f'{v:.4f}') for t, c, v in rows)


def step_time(t: np.ndarray, cmd: np.ndarray) -> float:
    """Return the time of the first zero command after a moving one."""
    moving = np.abs(cmd) > EPS
    for i in range(1, len(t)):
        if moving[i - 1] and not moving[i]:
            return float(t[i])
    raise ValueError('no step from a moving command to zero')


def analyze(t: np.ndarray, cmd: np.ndarray, v: np.ndarray) -> Brake:
    """Return the braking figures of one run."""
    t0 = step_time(t, cmd)
    measured = np.isfinite(v)
    t, speed = t[measured], np.abs(v[measured])
    steady = (t >= t0 - STEADY_SEC) & (t < t0)
    if not steady.any():
        raise ValueError('no samples before the step')
    v0 = float(speed[steady].mean())
    after = t >= t0
    ta, va = t[after], speed[after]
    band = (va <= 0.8 * v0) & (va >= 0.2 * v0)
    first_low = int(np.argmax(va < 0.2 * v0)) if (va < 0.2 * v0).any() else len(va)
    band[first_low:] = False
    if band.sum() < 2:
        raise ValueError('too few samples while braking (record faster or brake from higher)')
    slope, intercept = np.polyfit(ta[band], va[band], 1)
    decel = -float(slope)
    if decel <= 0.0:
        raise ValueError('the speed does not decrease after the step')
    reaction = max(0.0, (v0 - intercept) / slope - t0)
    stopped = va < 0.02 * v0
    end = int(np.argmax(stopped)) + 1 if stopped.any() else len(va)
    distance = float(np.sum(np.diff(ta[:end]) * (va[: end - 1] + va[1:end]) / 2.0))
    model = v0 * reaction + v0 * v0 / (2.0 * decel)
    return Brake(v0, float(reaction), decel, distance, model)


def report(paths: list[Path]) -> int:
    """Print one line per run and the values to configure; return an exit code."""
    results = []
    print(f'{"run":<24} {"v0":>6} {"t_r [s]":>8} {"a":>6} {"D meas":>7} {"D model":>8}')
    for path in paths:
        try:
            b = analyze(*read_run(path))
        except (OSError, KeyError, ValueError) as error:
            print(f'{path.name:<24} skipped: {error}')
            continue
        results.append(b)
        print(
            f'{path.name:<24} {b.v0:6.3f} {b.reaction_sec:8.3f} {b.decel:6.3f} '
            f'{b.distance:7.3f} {b.model_distance:8.3f}'
        )
    if not results:
        return 1
    reaction = max(b.reaction_sec for b in results)
    decel = min(b.decel for b in results)
    print(f'worst of {len(results)} runs: reaction {reaction:.3f} s, deceleration {decel:.3f}')
    return 0


def demo(out: Path, speed: float, decel: float, latency: float, noise: float, seed: int) -> None:
    """Write a run of the dharma_sim body (known decel and command latency) with speed noise."""
    from dharma_sim.core.body import Body, BodyLimits, Twist
    from dharma_sim.core.latency import CommandQueue
    from dharma_utils.math import Pose2D, default_rng

    body = Body(Pose2D(), BodyLimits(accel=1.0, decel=decel, max_dt=0.1))
    queue = CommandQueue(latency, timeout_sec=1.0, zero=Twist())
    rng = default_rng(seed)
    rows, dt = [], 1.0 / RATE_HZ
    for i in range(int(6.0 * RATE_HZ)):
        now = i * dt
        cmd = speed if 0.5 <= now < 4.0 else 0.0
        queue.push(now, Twist(cmd, 0.0, 0.0))
        body.step(now, queue.active(now))
        rows.append((now, cmd, body.twist.vx + float(rng.normal(0.0, noise))))
    write_run(out, rows)


def drive(args) -> None:
    """Send the step through the mux and record the measured speed (needs rclpy)."""
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    import rclpy

    rclpy.init()
    node = rclpy.create_node('brake_test')
    pub = node.create_publisher(Twist, f'control/remote/{args.source}/cmd_vel', 10)
    rows, state = [], {'cmd': 0.0, 't0': None}
    angular = args.axis == 'angular'

    def now() -> float:
        return node.get_clock().now().nanoseconds * 1e-9

    def on_odom(msg: Odometry):
        twist = msg.twist.twist
        if state['t0'] is not None:
            measured = twist.angular.z if angular else twist.linear.x
            rows.append((now() - state['t0'], state['cmd'], measured))

    def tick():
        elapsed = now() - state['t0']
        moving = args.zero_sec <= elapsed < args.zero_sec + args.hold
        cmd = args.speed if moving else 0.0
        if cmd != state['cmd']:
            rows.append((elapsed, cmd, math.nan))  # the exact time of the change
        state['cmd'] = cmd
        msg = Twist()
        if angular:
            msg.angular.z = state['cmd']
        else:
            msg.linear.x = state['cmd']
        pub.publish(msg)

    node.create_subscription(Odometry, args.odom, on_odom, 50)
    state['t0'] = now()
    node.create_timer(1.0 / RATE_HZ, tick)
    end = args.zero_sec + args.hold + args.stop_sec
    while rclpy.ok() and now() - state['t0'] < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    pub.publish(Twist())
    node.destroy_node()
    rclpy.shutdown()
    write_run(args.out, rows)


def main() -> int:
    """Parse the command line and run a subcommand."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('analyze', help='braking figures of recorded runs')
    a.add_argument('runs', nargs='+', type=Path)
    d = sub.add_parser('drive', help='step to zero through the mux and record (rclpy)')
    d.add_argument('--speed', type=float, required=True, help='m/s (rad/s with --axis angular)')
    d.add_argument('--axis', choices=('linear', 'angular'), default='linear')
    d.add_argument('--source', default='dashboard', help='remote source of the mux')
    d.add_argument('--odom', default='odom', help='nav_msgs/Odometry with the measured twist')
    d.add_argument('--hold', type=float, default=3.0, help='s at speed before the step')
    d.add_argument('--zero-sec', type=float, default=1.0, help='s of zeros before (re-arm)')
    d.add_argument('--stop-sec', type=float, default=2.0, help='s recorded after the step')
    d.add_argument('--out', type=Path, required=True)
    s = sub.add_parser('demo', help='a run of the dharma_sim body with known values')
    s.add_argument('--speed', type=float, default=0.5)
    s.add_argument('--decel', type=float, default=0.6)
    s.add_argument('--latency', type=float, default=0.12)
    s.add_argument('--noise', type=float, default=0.01)
    s.add_argument('--seed', type=int, default=0)
    s.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'analyze':
        return report(args.runs)
    if args.command == 'drive':
        if not math.isfinite(args.speed) or args.speed == 0.0:
            parser.error('--speed must be a finite, non-zero value')
        drive(args)
        return 0
    demo(args.out, args.speed, args.decel, args.latency, args.noise, args.seed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
