# Commissioning

Bringing HotDog up on a new M20 and a new substation, in order. Each step says how to see that
it works before the next one depends on it. Do the motion steps in an open area, slowly, with
someone holding the M20 remote and the hard emergency stop.

## 1. Network

The payload computer reaches three devices on its wired interface:

| Device              | Address (default)                                              | Used by                             |
| ------------------- | -------------------------------------------------------------- | ----------------------------------- |
| Lynx M20            | `10.21.31.103`, UDP 30000                                      | `m20_driver` (`ROBOT_IP`)           |
| RoboSense Airy × 2  | send to this computer, UDP 6699/7788 (front), 6698/7789 (rear) | `rslidar_sdk`                       |
| UniPod MT11         | `10.21.31.26` (factory `192.168.144.25`), TCP 37260, RTSP 8554 | `unipod_driver` (`POD_IP`)          |
| Hertzinno HZ-FA-371 | `192.168.2.204` (factory), HTTP 80                             | `inspection_node` (`acoustic.host`) |

Give the interface an address in each subnet the devices use, e.g. with netplan
(`/etc/netplan/60-hotdog.yaml`, then `sudo netplan apply`):

```yaml
network:
  version: 2
  ethernets:
    eth0: # the payload interface
      addresses: [10.21.31.50/24, 192.168.2.10/24]
```

Check: `ping 10.21.31.103`, `ping 10.21.31.26`, `ping 192.168.2.204`.

Operators reach the robot on the substation network for the reports: TCP **8088**
(`http://<robot>:8088/`, read-only) and SSH. Ask for both in the substation's network
permit; nothing else needs to be open towards the robot.

## 2. Install

```bash
git clone git@github.com:DarmawanRobotics/HotDog.git ~/dev/HotDog && cd ~/dev/HotDog
scripts/setup.sh install
scripts/setup.sh install service timesync
sudoedit /etc/hotdog/hotdog.env
```

| Variable             |                                                                      |
| -------------------- | -------------------------------------------------------------------- |
| `ROBOT_IP`           | the M20 (`10.21.31.103`)                                             |
| `DRIVER_PARAMS`      | this robot's m20_driver file, `/etc/hotdog/m20_driver.yaml` (step 3) |
| `PARAMS_FILE`        | this robot and site, `/etc/hotdog/site.yaml` (steps 5 - 9)           |
| `SITE`               | the site whose routes and inspection points are used                 |
| `POD_IP`             | the UniPod MT11                                                      |
| `HERTZINO_PASSWORD`  | the acoustic camera's password (never in a parameter file)           |
| `TELEGRAM_BOT_TOKEN` | the bot that sends the alerts (step 9)                               |

The file is read by systemd and bash: no comments after a value, quotes around values with
spaces. `scripts/setup.sh` checks every component.

## 3. The M20

Work through [m20_ros2: Verify on the real robot](https://github.com/DarmawanRobotics/m20_ros2#verify-on-the-real-robot)
with `ros2 launch m20_bringup bringup.launch.py` alone: reports, angle unit, stand, emergency
stop, takeover, one axis client, forward, the speed calibration per gait, turn and strafe signs,
direction Back. Put the results into a copy of the bringup's driver file:

```bash
sudo install -D -m 644 src/hotdog/config/m20_driver.yaml /etc/hotdog/m20_driver.yaml
sudoedit /etc/hotdog/m20_driver.yaml     # angle_unit, full_scale.<gait>.*, invert_*, ...
```

Keep `odom_frame: camera_init`, `base_frame: body` and `publish_tf: true`: they make the M20's
odometry HotDog's odometry.

## 4. The LiDARs

[hotdog_base: The Airy on the network](../src/hotdog_base/README.md#the-airy-on-the-network):
packets from both Airy reach this computer, `/lidar/front/points`, `/lidar/rear/points` and
`/lidar/points` at about 10 Hz, the rear cloud is behind the model in RViz (else fix
`cloud_merger_node` `input_rpy_deg` in the site file), the ground stays at `-base_height` while
the body tilts.

## 5. The robot profile and the stop

Measure `base_height` and the footprint with the payload mounted; a payload sticking out
belongs in the footprint. Measure the braking limits as the Dharma hub's Robot Profile guide
describes and keep `max_decel` / `reaction_time` at or below what was measured. Robot values go
into the site file (`/etc/hotdog/site.yaml`, `PARAMS_FILE`) under the nodes, or into a copy of
`config/robot.yaml` passed as `robot_params`. Check the protective field: walk towards the
robot while it drives slowly; it must stop before you, from every side.

## 6. The pod

[unipod_driver: first run](https://github.com/DarmawanRobotics/unipod_driver/blob/main/docs/first_run.md),
then with the whole robot running: `ros2 topic echo /inspection/status` shows
`pod_connected: true`. With AI super-resolution on, the temperature pixels are 1280 × 1024:
set `inspection_node` `thermal.width` / `thermal.height` in the site file.

## 7. The acoustic camera

The camera's web page: partial discharge mode, the analysis band and the imaging threshold the
site needs (the band of the manual for HV equipment). Then `inspection/status` shows
`acoustic_connected: true`. Run one detection in front of a known source (a corona gun, a
known defect) and compare the report with the camera's own result.

## 8. The site

The dock is the origin of everything HotDog teaches:

1. Put the M20 on its dock, start HotDog (`sudo systemctl start hotdog`), wait for
   `/localization/status` `LOCALIZED` (the odometry start is the origin).
2. Set the site: `SITE=<name>` in the env file (a new name creates the site), or
   `ros2 service call /site/load dharma_interfaces/srv/LoadSite "{site: <name>}"`.
3. Teach the route from the dock ([docs/operations.md](operations.md#teach-a-route)), with a
   target at each stop.
4. Set the day's air temperature (`thermal.ambient_c`), then run the first patrol at a low
   cruise speed (`path_follower_node speed.cruise: 0.3` in the site file) and check the reports.

## 9. Alerts

[hotdog_alerts: Set up](../src/hotdog_alerts/README.md#set-up): the bot token in the env file,
the crew's group in `alert_node` `telegram.chat_ids` of the site file, `robot_name`,
`language: id` when the crew prefers it, and `report_url` as the crew's phones reach the
robot. `ros2 service call /alerts/test std_srvs/srv/Trigger` must arrive in the group.

## 10. Time

Every stamp comes from one clock: `scripts/setup.sh install timesync` (chrony). The Airy are
stamped on arrival here (`use_lidar_clock: false`), so they need no PTP. `health/status` warns
when the clock drifts.
