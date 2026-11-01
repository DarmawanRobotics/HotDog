"""
patrol_node: route patrols from the dock, on demand (patrol/start) or on a schedule.

    ros2 launch hotdog_patrol patrol.launch.py
    ros2 launch hotdog_patrol patrol.launch.py robot_ns:=m20 sites_dir:=$HOME/.hotdog/sites

Same contract as the Dharma package launches (params_file, robot_params, use_sim_time,
log_level); the hotdog bringup starts it with its merged parameter file.
"""

from __future__ import annotations

from hotdog_base.utils import launch as hl
from launch import LaunchDescription
from launch.actions import OpaqueFunction

import dharma_utils.ros.launch as dl

PACKAGE = 'hotdog_patrol'
EXTRA = {
    'robot_ns': ('', 'robot driver namespace ({robot_ns}); empty: from the parameter files'),
    'sites_dir': ('', 'sites (routes); empty: from the parameter files'),
    'reports_dir': ('', 'reports; empty: from the parameter files'),
}


def nodes(context):
    """Build patrol_node from the arguments."""
    arg = hl.performer(context)
    files = hl.parameter_files(arg, PACKAGE, 'patrol.yaml', robot=False)
    values = hl.overrides(arg, robot_ns=arg('robot_ns'), sites_dir=arg('sites_dir'),
                          reports_dir=arg('reports_dir'))  # fmt: skip
    return [
        dl.node(
            package=PACKAGE,
            executable='patrol_node',
            name='patrol_node',
            output='screen',
            parameters=[*files, *dl.node_overrides('patrol_node', values)],
            ros_arguments=hl.ros_arguments(arg),
            respawn=True,
            respawn_delay=3.0,
        )
    ]


def generate_launch_description():
    """Declare the arguments; the node is built when the launch runs."""
    return LaunchDescription([*hl.declare(EXTRA), OpaqueFunction(function=nodes)])
