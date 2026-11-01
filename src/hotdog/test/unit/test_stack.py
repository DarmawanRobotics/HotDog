"""The stack composition: package launches, arguments, node names (no ROS)."""

from __future__ import annotations

from pathlib import Path

from hotdog import bringup, stack

CONFIG = Path(__file__).resolve().parents[2] / 'config'
CONTRACT = {'params_file', 'robot_params', 'use_sim_time', 'log_level'}


def options(**kwargs) -> stack.Options:
    return stack.Options(robot_params='/r.yaml', params_file='/p.yaml', **kwargs)


def by_package(includes) -> dict:
    return {i.package: i for i in includes}


def test_every_component_in_order():
    packages = [i.package for i in stack.compose(options())]
    assert packages == [
        'dharma_odometry',
        'dharma_localization',
        'hotdog_base',
        'dharma_perception',
        'dharma_mapping',
        'dharma_navigation',
        'dharma_control',
        'dharma_health',
        'hotdog_inspection',
        'hotdog_patrol',
    ]
    assert 'dharma_health' not in by_package(stack.compose(options(health=False)))
    assert 'hotdog_inspection' not in by_package(stack.compose(options(inspection=False)))
    assert 'hotdog_patrol' not in by_package(stack.compose(options(patrol=False)))
    assert 'hotdog_base' not in by_package(stack.compose(options(), sim=True))


def test_contract_arguments_reach_every_launch():
    o = options(use_sim_time='true', log_level='debug')
    for include in stack.compose(o):
        assert include.launch_file.endswith('.launch.py')
        assert include.arguments['params_file'] == '/p.yaml'
        assert include.arguments['robot_params'] == '/r.yaml'
        assert include.arguments['use_sim_time'] == 'true'
        assert include.arguments['log_level'] == 'debug'


def test_empty_arguments_are_never_passed():
    for include in stack.compose(options()):
        assert 'use_sim_time' not in include.arguments
        assert all(str(v).strip() for v in include.arguments.values())
    mapping = by_package(stack.compose(options()))['dharma_mapping'].arguments
    assert 'site' not in mapping
    assert 'sites_dir' not in mapping
    assert 'start_mapping' not in mapping  # HotDog never maps


def test_odometry_is_the_robots_own():
    includes = by_package(stack.compose(options()))
    assert includes['dharma_odometry'].arguments['method'] == 'external'
    assert 'leg_odom_topic' not in includes['dharma_odometry'].arguments


def test_robot_namespace_topics():
    includes = by_package(stack.compose(options(robot_ns='m20b')))
    nav = includes['dharma_navigation'].arguments
    assert (nav['battery_topic'], nav['odom_topic']) == ('/m20b/battery', '/m20b/odom')
    # the control mux is the only publisher of the driver's cmd_vel
    assert includes['dharma_control'].arguments['cmd_vel_topic'] == '/m20b/cmd_vel'
    assert all(not i.remappings for i in includes.values())


def test_sites():
    includes = by_package(stack.compose(options(site='gi_cawang', sites_dir='/s')))
    mapping = includes['dharma_mapping'].arguments
    assert (mapping['sites_dir'], mapping['site']) == ('/s', 'gi_cawang')
    assert includes['dharma_localization'].arguments['sites_dir'] == '/s'
    assert includes['hotdog_inspection'].arguments['sites_dir'] == '/s'
    assert includes['hotdog_patrol'].arguments == {
        **includes['hotdog_patrol'].arguments,
        'robot_ns': 'm20',
        'sites_dir': '/s',
    }
    assert 'inspection_node' in stack.SITES_NODES


def test_pod_nodes():
    names = stack.node_names(options())
    assert {'/unipod/unipod_driver', '/unipod/main/camera', '/unipod/sub/camera'} <= set(names)
    assert '/unipod/unipod_driver' not in stack.node_names(options(pod=False))
    assert '/unipod/unipod_driver' not in stack.node_names(options(), sim=True)
    assert '/inspection_node' in names


def test_lidar_source():
    includes = by_package(stack.compose(options(lidar='external')))
    assert includes['hotdog_base'].arguments['lidar'] == 'external'
    assert '/rslidar_sdk_node' in stack.node_names(options())
    assert '/rslidar_sdk_node' not in stack.node_names(options(lidar='external'))
    assert '/cloud_merger_node' in stack.node_names(options())


def test_perception_fiducials():
    perception = by_package(stack.compose(options(fiducials=True, camera_image='/c/img')))
    args = perception['dharma_perception'].arguments
    assert args['fiducials'] == 'true'
    assert args['camera_image'] == '/c/img'
    assert 'camera_info' not in args
    assert by_package(stack.compose(options()))['dharma_perception'].arguments['fiducials'] == (
        'false'
    )


def test_perception_aruco_detector():
    o = options(fiducials=True, fiducials_detector='aruco')
    perception = by_package(stack.compose(o))['dharma_perception'].arguments
    assert perception['fiducials_detector'] == 'aruco'
    names = stack.node_names(o)
    assert '/aruco_detector_node' in names and '/apriltag' not in names
    assert '/docking_node' in names
    assert 'aruco_detector_node' in stack.known_sections()


def test_sim_include():
    o = options(robot_ns='m20', site='mall_loop', sites_dir='/tmp/s')
    sim = stack.sim_include(o, world='', scenario='drift', rviz=True)
    assert (sim.package, sim.launch_file) == ('dharma_sim', 'sim.launch.py')
    assert CONTRACT - {'use_sim_time'} <= set(sim.arguments)
    assert sim.arguments['scenario'] == 'drift'
    assert sim.arguments['rviz'] == 'true'
    assert 'world' not in sim.arguments


def test_node_names():
    names = stack.node_names(options())
    assert '/health_monitor_node' in names
    assert '/apriltag' not in names
    assert names == sorted(names)
    sim = stack.node_names(options(), sim=True)
    assert '/sim_robot_node' in sim
    assert not {'/cloud_merger_node', '/rslidar_sdk_node'} & set(sim)


def test_shipped_files_only_configure_known_nodes():
    known = stack.known_sections()
    for name in ('stack.yaml', 'sim.yaml'):
        data = bringup.load_params(str(CONFIG / name))
        assert bringup.unknown_sections(data, known) == [], name
