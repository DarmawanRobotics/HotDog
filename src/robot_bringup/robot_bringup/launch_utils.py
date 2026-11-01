"""Launch-side helpers shared by robot.launch.py and sim.launch.py."""

from __future__ import annotations

from dataclasses import replace
import os

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    UnsetLaunchConfiguration,
)
from launch.launch_description_sources import (
    AnyLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import SetRemap

from dharma_utils.ros.launch import group
from robot_bringup import bringup, stack

PACKAGE = 'robot_bringup'

# name -> (environment variable or None, default, description)
ARGUMENTS = {
    'robot_params': (None, '', 'robot profile (robot.* parameters); empty: config/robot.yaml'),
    'params_file': (None, '', 'parameters on top of config/stack.yaml; empty: none'),
    'use_sim_time': (None, '', 'true | false; empty: from the parameter files'),
    'log_level': (None, 'info', 'debug, info, warn, error'),
    'robot_ns': ('ROBOT_NS', bringup.DEFAULT_ROBOT_NS, 'driver namespace (/<ns>/cmd_vel, odom)'),
    'robot_driver': ('ROBOT_DRIVER', '', '<package>[/<file>.launch.py]; empty: started elsewhere'),
    'odometry': ('ODOMETRY', 'fast_lio', 'fast_lio | leg_kilo | external'),
    'site': ('SITE', '', 'site to load (or to map); empty: from the files or the last one'),
    'sites_dir': ('SITES_DIR', '', 'sites directory; empty: from the parameter files'),
    'start_mapping': (None, 'false', 'true: map `site` from the start when it is new'),
    'fiducials': (None, 'true', 'camera throttle + tag detector'),
    'fiducials_detector': (None, 'apriltag', 'apriltag (apriltag_ros) | aruco'),
    'camera_image': (None, '', 'camera image topic; empty: the perception default'),
    'camera_info': (None, '', 'camera info topic; empty: the perception default'),
    'health': (None, 'true', 'start the health monitor'),
}
# Arguments only sim.launch.py declares (hidden from the includes like ARGUMENTS).
SIM_ONLY = ('world', 'scenario', 'rviz')


def share(package: str, *path: str) -> str:
    """Return a file in the installed share directory of a package."""
    try:
        root = get_package_share_directory(package)
    except PackageNotFoundError as error:
        raise bringup.BringupError(
            f'package {package!r} is not built in this workspace '
            '(vcs import --recursive src < dharma.repos, then colcon build)'
        ) from error
    return os.path.join(root, *path)


def declare(names, defaults: dict | None = None, env: bool = True) -> list:
    """Return DeclareLaunchArgument actions for ARGUMENTS (env: default from the environment)."""
    defaults = defaults or {}
    actions = []
    for name in names:
        variable, default, description = ARGUMENTS[name]
        default = defaults.get(name, default)
        if env and variable:
            default = EnvironmentVariable(variable, default_value=default)
        actions.append(DeclareLaunchArgument(name, default_value=default, description=description))
    return actions


def resolve(arg, sim: bool = False):
    """Validate the arguments and merge the parameter files; return (Options, log actions)."""
    robot_params = bringup.existing_file('robot_params', arg('robot_params'))
    robot_params = robot_params or share(PACKAGE, 'config', 'robot.yaml')
    profile = bringup.robot_profile(robot_params)
    files = [share(PACKAGE, 'config', 'stack.yaml')]
    if sim:
        files.append(share(PACKAGE, 'config', 'sim.yaml'))
    files.append(bringup.existing_file('params_file', arg('params_file')))
    options = stack.Options(
        robot_params=robot_params,
        params_file='',
        robot_ns=bringup.resolve_namespace(arg('robot_ns')),
        odometry='external' if sim else bringup.resolve_odometry(arg('odometry')),
        use_sim_time=arg('use_sim_time').strip(),
        log_level=arg('log_level').strip() or 'info',
        site=bringup.resolve_site(arg('site')),
        sites_dir=os.path.expanduser(arg('sites_dir').strip()),
        start_mapping=bringup.truthy(arg('start_mapping')),
        fiducials=bringup.truthy(arg('fiducials')),
        fiducials_detector=bringup.resolve_detector(arg('fiducials_detector')),
        camera_image=arg('camera_image').strip(),
        camera_info=arg('camera_info').strip(),
        health=bringup.truthy(arg('health')),
    )
    if options.start_mapping and not options.site:
        raise bringup.BringupError('start_mapping:=true needs site:=<name>')
    data = bringup.merge_files(files)
    data = bringup.with_sites_dir(data, stack.ROUTE_NODE, options.sites_dir)
    unknown = bringup.unknown_sections(data, stack.known_sections())
    if options.health:
        names = stack.node_names(options, sim=sim)
        data = bringup.with_expected_nodes(data, stack.HEALTH_NODE, names)
    options = replace(options, params_file=bringup.write_params(data))
    used = ', '.join(f for f in files if f)
    notes = [
        LogInfo(
            msg=f'{PACKAGE}: robot {profile.name} ({profile.kinematics}), ns /{options.robot_ns}, '
            f'odometry {options.odometry}, site {options.site or "(from files)"}, '
            f'parameters {robot_params}, {used}'
        ),
        *[LogInfo(msg=f'WARNING no node is called "{n}" (typo?)') for n in unknown],
        *[
            LogInfo(msg=f'WARNING "/**" {name}: on Foxy a node section of the defaults wins')
            for name in bringup.shared_parameters(data)
        ],
    ]
    return options, notes


def isolated(actions: list) -> GroupAction:
    """
    Return actions in their own scope that the bringup's own arguments never reach.

    Humble+ drops every caller configuration (forwarding=False). Foxy cannot, so the bringup's
    argument names are also unset inside the scope (a no-op where they are already dropped):
    an include sees only the arguments passed to it, on every distro.
    """
    hidden = [UnsetLaunchConfiguration(name) for name in (*ARGUMENTS, *SIM_ONLY)]
    return group([*hidden, *actions], scoped=True, forwarding=False)


def include_action(include: stack.Include) -> GroupAction:
    """Return a package launch in its own scope: only its explicit arguments reach it."""
    path = share(include.package, 'launch', include.launch_file)
    remaps = [SetRemap(src=src, dst=dst) for src, dst in include.remappings]
    source = PythonLaunchDescriptionSource(path)
    launch = IncludeLaunchDescription(source, launch_arguments=include.arguments.items())
    return isolated([*remaps, launch])


def driver_action(value: str, options: stack.Options) -> GroupAction | None:
    """Return the robot driver launch with namespace:=<robot_ns>, or None when unset."""
    driver = bringup.resolve_driver(value)
    if driver is None:
        return None
    package, launch_file = driver
    path = share(package, 'launch', launch_file)
    if not os.path.isfile(path):
        raise bringup.BringupError(f'robot_driver: {path} does not exist')
    args = stack.non_empty({'namespace': options.robot_ns, 'use_sim_time': options.use_sim_time})
    source = AnyLaunchDescriptionSource(path)
    launch = IncludeLaunchDescription(source, launch_arguments=args.items())
    return isolated([launch])


def performer(context):
    """Return arg(name) -> the evaluated launch argument."""
    return lambda name: LaunchConfiguration(name).perform(context)
