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
from hotdog import bringup, stack

PACKAGE = 'hotdog'

# name -> (environment variable or None, default, description)
ARGUMENTS = {
    'robot_params': (
        'ROBOT_PARAMS',
        '',
        'robot profile (robot.* parameters); empty: config/robot.yaml',
    ),
    'params_file': ('PARAMS_FILE', '', 'this robot and site on top of config/stack.yaml'),
    'use_sim_time': (None, '', 'true | false; empty: from the parameter files'),
    'log_level': (None, 'info', 'debug, info, warn, error'),
    'robot_ns': ('ROBOT_NS', bringup.DEFAULT_ROBOT_NS, 'driver namespace (/<ns>/cmd_vel, odom)'),
    'robot_driver': (
        'ROBOT_DRIVER',
        bringup.DEFAULT_DRIVER,
        '<package>[/<file>.launch.py]; empty: started elsewhere',
    ),
    'robot_ip': ('ROBOT_IP', '', 'the M20 (m20_bringup robot_ip); empty: its driver_params'),
    'driver_params': ('DRIVER_PARAMS', '', 'm20_driver parameters; empty: config/m20_driver.yaml'),
    'lidar': ('LIDAR', 'rslidar', 'rslidar: rslidar_sdk for both Airy | external: clouds exist'),
    'site': ('SITE', '', 'site to load; empty: from the files or the last one'),
    'sites_dir': ('SITES_DIR', '~/.hotdog/sites', 'sites: taught routes, inspection points'),
    'inspection': ('INSPECTION', 'true', 'inspection at the stop points (inspection_node)'),
    'patrol': (
        'PATROL',
        'true',
        'patrols from the dock, on demand or on a schedule (patrol_node)',
    ),
    'reports': (
        'REPORTS',
        'true',
        'HTML reports, retention and the report server on port 8088 (report_node)',
    ),
    'alerts': (
        'ALERTS',
        'true',
        'Telegram and webhook alerts (alert_node; TELEGRAM_BOT_TOKEN, telegram.chat_ids)',
    ),
    'pod': ('POD', 'true', 'unipod_driver for the UniPod MT11 (gimbal, cameras, temperatures)'),
    'pod_ip': ('POD_IP', '', 'the UniPod MT11; empty: unipod_driver default (10.21.31.26)'),
    'fiducials': (None, 'false', 'camera throttle + tag detector'),
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
        lidar='external' if sim else bringup.resolve_lidar(arg('lidar')),
        use_sim_time=arg('use_sim_time').strip(),
        log_level=arg('log_level').strip() or 'info',
        site=bringup.resolve_site(arg('site')),
        sites_dir=os.path.expanduser(arg('sites_dir').strip()),
        fiducials=bringup.truthy(arg('fiducials')),
        fiducials_detector=bringup.resolve_detector(arg('fiducials_detector')),
        camera_image=arg('camera_image').strip(),
        camera_info=arg('camera_info').strip(),
        health=bringup.truthy(arg('health')),
        inspection=bringup.truthy(arg('inspection')),
        patrol=bringup.truthy(arg('patrol')),
        reports=bringup.truthy(arg('reports')),
        alerts=bringup.truthy(arg('alerts')),
        pod=False if sim else bringup.truthy(arg('pod')),
    )
    data = bringup.merge_files(files)
    data = bringup.with_sites_dir(data, stack.SITES_NODES, options.sites_dir)
    unknown = bringup.unknown_sections(data, stack.known_sections())
    if options.health:
        names = stack.node_names(options, sim=sim)
        if not sim:
            names += bringup.driver_nodes(arg('robot_driver'), options.robot_ns)
        data = bringup.with_expected_nodes(data, stack.HEALTH_NODE, names)
    options = replace(options, params_file=bringup.write_params(data))
    used = ', '.join(f for f in files if f)
    notes = [
        LogInfo(
            msg=f'{PACKAGE}: robot {profile.name} ({profile.kinematics}), ns /{options.robot_ns}, '
            f'lidar {"simulated" if sim else options.lidar}, '
            f'site {options.site or "(from files)"}, '
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


def driver_action(arg, options: stack.Options) -> GroupAction | None:
    """Return the robot driver launch with namespace:=<robot_ns>, or None when unset."""
    driver = bringup.resolve_driver(arg('robot_driver'))
    if driver is None:
        return None
    package, launch_file = driver
    path = share(package, 'launch', launch_file)
    if not os.path.isfile(path):
        raise bringup.BringupError(f'robot_driver: {path} does not exist')
    values = {'namespace': options.robot_ns, 'use_sim_time': options.use_sim_time}
    if package == bringup.DEFAULT_DRIVER:  # m20_bringup: this product's driver settings
        params = bringup.existing_file('driver_params', arg('driver_params'))
        values['driver_params'] = params or share(PACKAGE, 'config', 'm20_driver.yaml')
        values['robot_ip'] = arg('robot_ip').strip()
    args = stack.non_empty(values)
    source = AnyLaunchDescriptionSource(path)
    launch = IncludeLaunchDescription(source, launch_arguments=args.items())
    return isolated([launch])


def pod_action(arg, options: stack.Options) -> GroupAction | None:
    """Return unipod_driver.launch.py in the unipod namespace, or None when off."""
    if not options.pod:
        return None
    path = share('unipod_driver', 'launch', 'unipod_driver.launch.py')
    args = stack.non_empty({'namespace': stack.POD_NAMESPACE, 'ip': arg('pod_ip').strip()})
    source = PythonLaunchDescriptionSource(path)
    return isolated([IncludeLaunchDescription(source, launch_arguments=args.items())])


def performer(context):
    """Return arg(name) -> the evaluated launch argument."""
    return lambda name: LaunchConfiguration(name).perform(context)
