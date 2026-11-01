"""
The whole robot in one launch: the M20 driver, its LiDARs, the pod, the stack and inspection.

    ros2 launch hotdog robot.launch.py                        # M20 driver, LiDARs, the stack
    ros2 launch hotdog robot.launch.py site:=gi_cawang robot_ip:=10.21.31.103
    ros2 launch hotdog robot.launch.py robot_driver:= lidar:=external   # both run elsewhere

Every package launch gets robot_params:=config/robot.yaml and one parameter file merged from
config/stack.yaml and params_file (later wins), with the started nodes added to the health
monitor's nodes.expected. The composition itself is in hotdog/stack.py.
"""

from __future__ import annotations

from launch import LaunchDescription
from launch.actions import OpaqueFunction

from hotdog import launch_utils as lu
from hotdog import stack


def launch_setup(context):
    """Validate the arguments and build the robot driver and the stack."""
    arg = lu.performer(context)
    options, notes = lu.resolve(arg)
    devices = [lu.driver_action(arg, options), lu.pod_action(arg, options)]
    actions = [*notes, *(d for d in devices if d is not None)]
    return actions + [lu.include_action(i) for i in stack.compose(options)]


def generate_launch_description():
    """Declare the arguments (robot_ns, robot_driver, lidar, site, sites_dir ...: env too)."""
    return LaunchDescription([*lu.declare(lu.ARGUMENTS), OpaqueFunction(function=launch_setup)])
