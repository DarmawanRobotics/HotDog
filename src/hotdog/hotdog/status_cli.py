"""
`ros2 run hotdog status`: the robot at a glance.

The latched statuses of the stack, the battery, the alert queue, the report server and the
disk.

    ros2 run hotdog status            # waits up to 3 s for the statuses
    ros2 run hotdog status --wait 6 --no-color
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState

from dharma_interfaces.msg import ControlStatus, HealthStatus, LocalizationStatus, NavigationStatus
from dharma_utils.ros import LATCHED
from hotdog.status import lines
from hotdog_interfaces.msg import InspectionStatus, PatrolStatus

FIELDS = {
    'patrol': (PatrolStatus, 'patrol/status', (
        'state', 'route', 'elapsed_sec', 'points', 'critical', 'warning', 'attention',
        'next_scheduled', 'message')),
    'health': (HealthStatus, 'health/status', ('level', 'speed_scale', 'issues')),
    'localization': (LocalizationStatus, 'localization/status', ('state', 'source', 'sigma_xy')),
    'control': (ControlStatus, 'control/status', ('mode', 'estop', 'estop_reasons', 'field')),
    'inspection': (InspectionStatus, 'inspection/status', (
        'state', 'pod_connected', 'acoustic_connected', 'ambient_c', 'points', 'targets',
        'last_point', 'last_severity')),
    'navigation': (NavigationStatus, 'navigation/status', (
        'state', 'pause_reasons', 'remaining', 'count')),
}  # fmt: skip


def as_dict(msg, fields) -> dict:
    """Return the fields of a message as plain values."""
    out = {}
    for f in fields:
        value = getattr(msg, f)
        out[f] = (
            list(value) if isinstance(value, (list, tuple)) or hasattr(value, 'tolist') else value
        )
    return out


def extras(args) -> dict:
    """Return the alert queue, the report server and the disk of the reports."""
    alerts = os.path.expanduser(args.alerts_dir)
    queued = (
        len([n for n in os.listdir(alerts) if n.endswith('.json')]) if os.path.isdir(alerts) else 0
    )
    reports = os.path.expanduser(args.reports_dir)
    out = {'alerts': f'{queued} waiting to be sent' if queued else 'nothing waiting'}
    out['reports'] = f'http://{host_address()}:{args.port}/'
    if os.path.isdir(reports):
        free = shutil.disk_usage(reports).free / 1024**3
        out['disk'] = f'{free:.1f} GB free under {reports}'
    return out


def host_address() -> str:
    """Return this computer's address on the default route (its hostname as a fallback)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('10.255.255.255', 1))
        return probe.getsockname()[0]
    except OSError:
        return socket.gethostname()
    finally:
        probe.close()


def main(argv=None):
    """Print the status once."""
    parser = argparse.ArgumentParser(description='HotDog at a glance')
    parser.add_argument('--wait', type=float, default=3.0, help='seconds to wait for statuses')
    parser.add_argument('--robot-ns', default=os.environ.get('ROBOT_NS', 'm20'))
    parser.add_argument('--alerts-dir', default='~/.hotdog/alerts')
    parser.add_argument('--reports-dir', default='~/.hotdog/reports')
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--no-color', action='store_true')
    args, ros_args = parser.parse_known_args(argv)
    rclpy.init(args=ros_args)
    node = rclpy.create_node('hotdog_status')
    snapshot: dict = {}
    for part, (kind, topic, fields) in FIELDS.items():
        node.create_subscription(kind, topic, lambda m, p=part, f=fields: snapshot.__setitem__(
            p, as_dict(m, f)), LATCHED)  # fmt: skip
    battery = f'/{args.robot_ns.strip("/")}/battery'
    node.create_subscription(BatteryState, battery,
                             lambda m: snapshot.__setitem__('battery', float(m.percentage)),
                             qos_profile_sensor_data)  # fmt: skip
    deadline = time.monotonic() + args.wait
    wanted = {*FIELDS, 'battery'}
    while time.monotonic() < deadline and not wanted <= set(snapshot):
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    rclpy.shutdown()
    snapshot.update(extras(args))
    color = sys.stdout.isatty() and not args.no_color
    print('\n'.join(lines(snapshot, color)))
    return 0 if 'patrol' in snapshot else 1


if __name__ == '__main__':
    sys.exit(main())
