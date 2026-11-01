"""
The composition of HotDog: the Dharma stack on the M20's own odometry, plus its LiDARs.

This is the one place to adjust when a package's launch contract changes. Every package launch
accepts params_file, robot_params, use_sim_time and log_level; only non-empty arguments are
passed, so an unset one never hides a value from a parameter file.

HotDog maps nothing: odometry is the robot's own (m20_driver publishes camera_init -> body),
localization takes the odometry start as the map origin, and dharma_mapping only keeps the
sites and their taught routes (its grid mapper stays idle).
"""

from __future__ import annotations

from dataclasses import dataclass, field

HEALTH_NODE = 'health_monitor_node'
ROUTE_NODE = 'path_loader_node'  # loads taught routes from sites_dir
# nodes that read sites_dir: the bringup gives them all the one of the launch
SITES_NODES = (
    'localization_node',
    'site_manager_node',
    'route_recorder_node',
    ROUTE_NODE,
    'inspection_node',
    'patrol_node',
)
LIDAR_SOURCES = ('rslidar', 'external')


@dataclass(frozen=True)
class Include:
    """One package launch file with its arguments and the remappings of its nodes."""

    package: str
    launch_file: str
    arguments: dict = field(default_factory=dict)
    remappings: tuple = ()


@dataclass(frozen=True)
class Options:
    """The resolved bringup arguments."""

    robot_params: str
    params_file: str
    robot_ns: str = 'm20'
    lidar: str = 'rslidar'  # rslidar: rslidar_sdk for both Airy; external: clouds exist
    use_sim_time: str = ''
    log_level: str = 'info'
    site: str = ''
    sites_dir: str = ''
    fiducials: bool = False
    fiducials_detector: str = 'apriltag'  # apriltag | aruco
    camera_image: str = ''
    camera_info: str = ''
    health: bool = True
    inspection: bool = True  # inspection_node, the follower's hook at every stop point
    pod: bool = True  # unipod_driver for the UniPod MT11
    patrol: bool = True  # patrol_node: patrols from the dock, on demand or on a schedule


# component -> (package, launch file, nodes it starts, by node name)
COMPONENTS = {
    'odometry': ('dharma_odometry', 'odometry.launch.py', ('odometry_monitor_node',)),
    'localization': ('dharma_localization', 'localization.launch.py', ('localization_node',)),
    'base': ('hotdog_base', 'base.launch.py', ('cloud_merger_node',)),
    'perception': ('dharma_perception', 'perception.launch.py', ('lidar_sector_node',)),
    'mapping': (
        'dharma_mapping',
        'mapping.launch.py',
        ('grid_mapper_node', 'site_manager_node', 'route_recorder_node'),
    ),
    'navigation': (
        'dharma_navigation',
        'navigation.launch.py',
        (
            'planner_node',
            'path_loader_node',
            'path_follower_node',
            'obstacle_avoidance_node',
            'docking_node',
        ),
    ),
    'control': ('dharma_control', 'control.launch.py', ('control_mux_node',)),
    'health': ('dharma_health', 'health.launch.py', (HEALTH_NODE,)),
    'inspection': ('hotdog_inspection', 'inspection.launch.py', ('inspection_node',)),
    'patrol': ('hotdog_patrol', 'patrol.launch.py', ('patrol_node',)),
}
RSLIDAR_NODE = 'rslidar_sdk_node'  # reads its own file (config/rslidar.yaml), no parameters
POD_NAMESPACE = 'unipod'
POD_NODES = ('unipod_driver', 'main/camera', 'sub/camera')  # unipod_driver.launch.py
FIDUCIAL_NODES = ('apriltag_throttle', 'apriltag')
DETECTOR_NODES = {'apriltag': 'apriltag', 'aruco': 'aruco_detector_node'}
SIM = ('dharma_sim', 'sim.launch.py', ('sim_robot_node',))
ROBOT_ONLY = ('base',)  # the simulator publishes its own cloud (and has no pod)


def non_empty(arguments: dict) -> dict:
    """Return the arguments that are set (an empty one must never override a file)."""
    return {k: str(v) for k, v in arguments.items() if v is not None and str(v).strip()}


def flag(value: bool) -> str:
    """Return a launch bool."""
    return 'true' if value else 'false'


def common(o: Options) -> dict:
    """Return the arguments every package launch accepts."""
    return {
        'params_file': o.params_file,
        'robot_params': o.robot_params,
        'use_sim_time': o.use_sim_time,
        'log_level': o.log_level,
    }


def component_arguments(o: Options) -> dict:
    """Return the launch arguments of every component (before dropping empty ones)."""
    driver = f'/{o.robot_ns}'
    return {
        # the robot's own odometry: nothing to start, the monitor reads it (stack.yaml)
        'odometry': {'method': 'external'},
        'localization': {'sites_dir': o.sites_dir},
        'base': {'lidar': o.lidar},
        'perception': {
            'fiducials': flag(o.fiducials),
            'fiducials_detector': o.fiducials_detector,
            'camera_image': o.camera_image,
            'camera_info': o.camera_info,
        },
        'mapping': {'sites_dir': o.sites_dir, 'site': o.site},
        'navigation': {'battery_topic': f'{driver}/battery', 'odom_topic': f'{driver}/odom'},
        'control': {'cmd_vel_topic': f'{driver}/cmd_vel'},  # the mux drives the robot
        'health': {},
        'inspection': {'sites_dir': o.sites_dir},
        'patrol': {'robot_ns': o.robot_ns, 'sites_dir': o.sites_dir},
    }


def components(o: Options, sim: bool = False) -> list[str]:
    """Return the components to start, in launch order."""
    wanted = {'health': o.health, 'inspection': o.inspection, 'patrol': o.patrol}
    return [
        name for name in COMPONENTS if wanted.get(name, True) and not (sim and name in ROBOT_ONLY)
    ]


def compose(o: Options, sim: bool = False) -> list[Include]:
    """Return the package launch files of the stack with their arguments."""
    arguments = component_arguments(o)
    out = []
    for name in components(o, sim):
        package, launch_file, _ = COMPONENTS[name]
        args = non_empty({**common(o), **arguments[name]})
        out.append(Include(package, launch_file, args))
    return out


def sim_include(o: Options, world: str = '', scenario: str = '', rviz: bool = False) -> Include:
    """Return the simulated robot (driver, LiDAR, IMU and odometry in one node)."""
    package, launch_file, _ = SIM
    args = {
        **common(o),
        'world': world,
        'scenario': scenario,
        'robot_ns': o.robot_ns,
        'site': o.site,
        'sites_dir': o.sites_dir,
        'rviz': flag(rviz),
    }
    return Include(package, launch_file, non_empty(args))


def node_names(o: Options, sim: bool = False) -> list[str]:
    """Return the fully qualified names of every node the bringup starts."""
    names = [n for c in components(o, sim) for n in COMPONENTS[c][2]]
    if not sim and o.lidar == 'rslidar':
        names.append(RSLIDAR_NODE)
    if not sim and o.pod:
        names += [f'{POD_NAMESPACE}/{n}' for n in POD_NODES]
    if o.fiducials:
        names += (FIDUCIAL_NODES[0], DETECTOR_NODES[o.fiducials_detector])
    if sim:
        names += SIM[2]
    return sorted(f'/{n}' for n in names)


def known_sections() -> list[str]:
    """Return every node name a parameter file of the bringup may configure."""
    names = [n for c in COMPONENTS.values() for n in c[2]]
    return sorted({*names, *FIDUCIAL_NODES, *DETECTOR_NODES.values(), *SIM[2]})
