"""
The M20's LiDARs: rslidar_sdk for both Airy and cloud_merger_node for the merged cloud.

    ros2 launch hotdog_base base.launch.py
    ros2 launch hotdog_base base.launch.py lidar:=external        # clouds come from elsewhere
    ros2 launch hotdog_base base.launch.py rslidar_config:=$HOME/rslidar.yaml

Same contract as the Dharma package launches (params_file, robot_params, use_sim_time,
log_level); the hotdog bringup starts it with its merged parameter file.
"""

from __future__ import annotations

import os

from hotdog_base.utils import launch as hl
from launch import LaunchDescription
from launch.actions import OpaqueFunction

import dharma_utils.ros.launch as dl

PACKAGE = 'hotdog_base'
LIDAR_SOURCES = ('rslidar', 'external')
EXTRA = {
    'lidar': ('rslidar', 'rslidar: start rslidar_sdk for both Airy; external: clouds exist'),
    'rslidar_config': ('', 'rslidar_sdk config file; empty: config/rslidar.yaml'),
}


def rslidar_node(arg) -> list:
    """Return rslidar_sdk with its configuration file, or nothing for external clouds."""
    source = arg('lidar') or LIDAR_SOURCES[0]
    if source not in LIDAR_SOURCES:
        raise ValueError(f'lidar:={source!r}, use one of {LIDAR_SOURCES}')
    if source == 'external':
        return []
    path = os.path.expanduser(arg('rslidar_config')) or hl.share(PACKAGE, 'config', 'rslidar.yaml')
    if not os.path.isfile(path):
        raise FileNotFoundError(f'rslidar_config:={path} does not exist')
    return [
        dl.node(
            package='rslidar_sdk',
            executable='rslidar_sdk_node',
            name='rslidar_sdk_node',
            output='screen',
            parameters=[{'config_path': path}],
            respawn=True,
            respawn_delay=2.0,
        )
    ]


def nodes(context):
    """Build rslidar_sdk and the merger from the arguments."""
    arg = hl.performer(context)
    files = hl.parameter_files(arg, PACKAGE, 'base.yaml')
    merger = dl.node(
        package=PACKAGE,
        executable='cloud_merger_node',
        name='cloud_merger_node',
        output='screen',
        parameters=[*files, *dl.node_overrides('cloud_merger_node', hl.overrides(arg))],
        ros_arguments=hl.ros_arguments(arg),
        respawn=True,
        respawn_delay=2.0,
    )
    return [*rslidar_node(arg), merger]


def generate_launch_description():
    """Declare the arguments; the nodes are built when the launch runs."""
    return LaunchDescription([*hl.declare(EXTRA), OpaqueFunction(function=nodes)])
