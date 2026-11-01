"""
alert_node: findings, patrols and health ERROR to Telegram and a webhook.

    ros2 launch hotdog_alerts alerts.launch.py
    TELEGRAM_BOT_TOKEN=... ros2 launch hotdog_alerts alerts.launch.py

Same contract as the Dharma package launches (params_file, robot_params, use_sim_time,
log_level); the hotdog bringup starts it with its merged parameter file.
"""

from __future__ import annotations

from hotdog_base.utils import launch as hl
from launch import LaunchDescription
from launch.actions import OpaqueFunction

import dharma_utils.ros.launch as dl

PACKAGE = 'hotdog_alerts'
EXTRA = {
    'reports_dir': ('', 'reports (patrol page links); empty: from the parameter files'),
}


def nodes(context):
    """Build alert_node from the arguments."""
    arg = hl.performer(context)
    files = hl.parameter_files(arg, PACKAGE, 'alerts.yaml', robot=False)
    values = hl.overrides(arg, reports_dir=arg('reports_dir'))
    return [
        dl.node(
            package=PACKAGE,
            executable='alert_node',
            name='alert_node',
            output='screen',
            parameters=[*files, *dl.node_overrides('alert_node', values)],
            ros_arguments=hl.ros_arguments(arg),
            respawn=True,
            respawn_delay=3.0,
        )
    ]


def generate_launch_description():
    """Declare the arguments; the node is built when the launch runs."""
    return LaunchDescription([*hl.declare(EXTRA), OpaqueFunction(function=nodes)])
