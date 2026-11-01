"""
The same stack on the simulated robot of dharma_sim (odometry external), no hardware.

    ros2 launch robot_bringup sim.launch.py rviz:=true
    ros2 launch robot_bringup sim.launch.py scenario:=person_crossing
    ros2 topic pub --once /sim/obstacles geometry_msgs/msg/PoseArray \
        "{poses: [{position: {x: 2.0, y: -3.0}}]}"

The site (default mall_loop under /tmp/dharma_sim/sites) is drawn from the world when it has no
map yet. config/sim.yaml adapts the stack to the simulator (PointCloud2 input, no camera).
"""

from __future__ import annotations

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction

from robot_bringup import bringup, stack
from robot_bringup import launch_utils as lu

SIM_ARGUMENTS = [n for n in lu.ARGUMENTS if n not in ('robot_driver', 'odometry')]
SIM_DEFAULTS = {'site': 'mall_loop', 'sites_dir': '/tmp/dharma_sim/sites', 'fiducials': 'false'}


def launch_setup(context):
    """Start the simulated robot, then the stack against it."""
    arg = lu.performer(context)
    options, notes = lu.resolve(arg, sim=True)
    sim = stack.sim_include(options, arg('world'), arg('scenario'), bringup.truthy(arg('rviz')))
    return [*notes, *(lu.include_action(i) for i in [sim, *stack.compose(options)])]


def generate_launch_description():
    """Declare the arguments of the robot launch (no driver, odometry) and of the simulator."""
    return LaunchDescription(
        [
            *lu.declare(SIM_ARGUMENTS, SIM_DEFAULTS, env=False),
            DeclareLaunchArgument(
                'world', default_value='', description='world file or name; empty: mall_loop'
            ),
            DeclareLaunchArgument(
                'scenario', default_value='', description='scenario file or name; empty: none'
            ),
            DeclareLaunchArgument('rviz', default_value='false', description='RViz (dharma_rviz)'),
            OpaqueFunction(function=launch_setup),
        ]
    )
