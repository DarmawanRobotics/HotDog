"""
inspection_node: thermal inspection at the stop points with the UniPod MT11.

    ros2 launch hotdog_inspection inspection.launch.py
    ros2 launch hotdog_inspection inspection.launch.py sites_dir:=$HOME/.hotdog/sites

Same contract as the Dharma package launches (params_file, robot_params, use_sim_time,
log_level); the hotdog bringup starts it with its merged parameter file.
"""

from __future__ import annotations

from hotdog_base.utils import launch as hl
from launch import LaunchDescription
from launch.actions import OpaqueFunction

import dharma_utils.ros.launch as dl

PACKAGE = 'hotdog_inspection'
EXTRA = {
    'sites_dir': ('', 'sites (inspection.yaml per site); empty: from the parameter files'),
    'reports_dir': ('', 'reports; empty: from the parameter files'),
}


def nodes(context):
    """Build inspection_node from the arguments."""
    arg = hl.performer(context)
    files = hl.parameter_files(arg, PACKAGE, 'inspection.yaml')
    values = hl.overrides(arg, sites_dir=arg('sites_dir'), reports_dir=arg('reports_dir'))
    return [
        dl.node(
            package=PACKAGE,
            executable='inspection_node',
            name='inspection_node',
            output='screen',
            parameters=[*files, *dl.node_overrides('inspection_node', values)],
            ros_arguments=hl.ros_arguments(arg),
            respawn=True,
            respawn_delay=3.0,
        )
    ]


def generate_launch_description():
    """Declare the arguments; the node is built when the launch runs."""
    return LaunchDescription([*hl.declare(EXTRA), OpaqueFunction(function=nodes)])
