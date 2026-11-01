"""
The same stack on the simulated robot of dharma_sim, no M20, LiDARs or pod needed.

    ros2 launch hotdog sim.launch.py rviz:=true
    ros2 launch hotdog sim.launch.py scenario:=person_crossing
    ros2 topic pub --once /sim/obstacles geometry_msgs/msg/PoseArray \
        "{poses: [{position: {x: 2.0, y: -3.0}}]}"

The site (default mall_loop under /tmp/dharma_sim/sites) is drawn from the world when it has no
map yet. config/sim.yaml adapts the stack to the simulator (PointCloud2 input, no camera).
"""

from __future__ import annotations

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction

from hotdog import bringup, stack
from hotdog import launch_utils as lu

ROBOT_ONLY = ('robot_driver', 'robot_ip', 'driver_params', 'lidar')
SIM_ARGUMENTS = [n for n in lu.ARGUMENTS if n not in ROBOT_ONLY]
SIM_DEFAULTS = {'site': 'mall_loop', 'sites_dir': '/tmp/dharma_sim/sites', 'fiducials': 'false'}


def launch_setup(context):
    """Start the simulated robot, then the stack against it."""
    arg = lu.performer(context)
    options, notes = lu.resolve(arg, sim=True)
    sim = stack.sim_include(options, arg('world'), arg('scenario'), bringup.truthy(arg('rviz')))
    includes = [sim, *stack.compose(options, sim=True)]
    return [*notes, *(lu.include_action(i) for i in includes)]


def generate_launch_description():
    """Declare the arguments of the robot launch (no driver, no LiDARs) and the simulator."""
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
