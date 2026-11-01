"""
report_node: HTML patrol reports, retention and the read-only report server.

    ros2 launch hotdog_reports reports.launch.py
    ros2 launch hotdog_reports reports.launch.py reports_dir:=$HOME/.hotdog/reports

Same contract as the Dharma package launches (params_file, robot_params, use_sim_time,
log_level); the hotdog bringup starts it with its merged parameter file.
"""

from __future__ import annotations

from hotdog_base.utils import launch as hl
from launch import LaunchDescription
from launch.actions import OpaqueFunction

import dharma_utils.ros.launch as dl

PACKAGE = 'hotdog_reports'
EXTRA = {
    'reports_dir': ('', 'reports; empty: from the parameter files'),
}


def nodes(context):
    """Build report_node from the arguments."""
    arg = hl.performer(context)
    files = hl.parameter_files(arg, PACKAGE, 'reports.yaml', robot=False)
    values = hl.overrides(arg, reports_dir=arg('reports_dir'))
    return [
        dl.node(
            package=PACKAGE,
            executable='report_node',
            name='report_node',
            output='screen',
            parameters=[*files, *dl.node_overrides('report_node', values)],
            ros_arguments=hl.ros_arguments(arg),
            respawn=True,
            respawn_delay=3.0,
        )
    ]


def generate_launch_description():
    """Declare the arguments; the node is built when the launch runs."""
    return LaunchDescription([*hl.declare(EXTRA), OpaqueFunction(function=nodes)])
