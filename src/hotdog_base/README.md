# hotdog_base

The Lynx M20 under HotDog: both RoboSense Airy LiDARs through `rslidar_sdk`, one merged,
self-filtered and leveled cloud in `base_link` for perception and health, and the launch helpers
the HotDog packages share.

## Nodes

| Node                | Executable          |                                                                                   |
| ------------------- | ------------------- | --------------------------------------------------------------------------------- |
| `rslidar_sdk_node`  | `rslidar_sdk`       | both Airy from `config/rslidar.yaml`: `/lidar/front/points`, `/lidar/rear/points` |
| `cloud_merger_node` | `cloud_merger_node` | the two clouds as `/lidar/points` in `base_link`                                  |

`cloud_merger_node`:

| Interface                                   | Type                      |                                                          |
| ------------------------------------------- | ------------------------- | -------------------------------------------------------- |
| `/lidar/front/points`, `/lidar/rear/points` | `sensor_msgs/PointCloud2` | inputs (`inputs`), any frame on TF                       |
| `/m20/imu`                                  | `sensor_msgs/Imu`         | body attitude for leveling (`imu_topic`)                 |
| `/lidar/points`                             | `sensor_msgs/PointCloud2` | merged xyz in `base_link`, stamped with the newest input |

- **Frames.** Each input goes through TF (`front_lidar_link`, `rear_lidar_link` of
  `m20_description`) and an extra roll, pitch, yaw per input (`input_rpy_deg`): the M20 model
  gives the rear LiDAR no rotation, the default turns it by 180°. Check both on the robot.
- **Fail safe.** A merged cloud goes out when the first input arrives and, with
  `require_all`, only while every other input is fresh (`max_age_sec`). A silent side stops
  the output, so perception publishes its scans BLOCKED instead of a scan blind on one side.
- **Self filter and crop.** Points inside the footprint (robot profile) grown by
  `self_margin`, up to `self_height` above `base_link`, are the robot (legs, pod, Hertzinno);
  points beyond `range_max` or `height_max` above the floor are dropped.
- **Leveling.** The M20's odometry is planar, so perception cannot level the cloud from TF.
  With `level_source: imu` the body's roll and pitch (from `/m20/imu`, once m20_driver knows its
  angle unit) are removed here; perception runs with `filter.level_source: none`.

Every parameter: [config/base.yaml](config/base.yaml) and
`ros2 param describe /cloud_merger_node <name>`.

## Launch

```bash
ros2 launch hotdog_base base.launch.py                       # rslidar_sdk + merger
ros2 launch hotdog_base base.launch.py lidar:=external       # clouds published elsewhere
ros2 launch hotdog_base base.launch.py rslidar_config:=$HOME/rslidar.yaml
```

Same contract as the Dharma launches (`params_file`, `robot_params`, `use_sim_time`,
`log_level`); `ros2 launch hotdog robot.launch.py` starts it with the merged parameters.

## The Airy on the network

Each Airy sends its packets (MSOP, DIFOP) to one destination address and port pair, set in its
web page. HotDog expects this computer as the destination of both, the front one on
6699 / 7788, the rear one on 6698 / 7789 ([config/rslidar.yaml](config/rslidar.yaml)). On a new
robot:

1. `sudo tcpdump -ni any udp port 6699 or udp port 6698` shows packets from both LiDARs. If not,
   the LiDARs send to the robot's own computer: change their destination (or the ports in
   `rslidar.yaml` to what they send) in the LiDAR web page.
2. `ros2 topic hz /lidar/front/points /lidar/rear/points /lidar/points`: about 10 Hz each.
3. RViz, fixed frame `base_link`, the robot in front of a wall: the wall in `/lidar/points`
   is in front of the model, a wall behind is behind it. Otherwise fix `input_rpy_deg`.
4. Tilt the robot by hand (or let it walk a slope): the ground in `/lidar/points` stays at
   `-base_height`.

When the clouds cannot reach this computer, publish them from where they arrive and launch
with `lidar:=external` (the merger only needs the two topics).

## Test

```bash
colcon test --packages-select hotdog_base && colcon test-result --verbose
```

`test/unit` checks the frames, the self filter, the crop, staleness and leveling without ROS;
`test/ros` runs the node with two clouds and static TF.
