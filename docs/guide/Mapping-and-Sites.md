# Mapping and Sites

A **site** is a place the robot works in: its occupancy map, its fiducial tags and its taught
routes, in one folder under `sites_dir`:

```
<sites_dir>/<site>/
├── map.yaml, map.pgm           occupancy map (map_server format, with size and CRC)
├── map.yaml.bak, map.pgm.bak   the previous map
├── tags.json                   fiducial poses in the map frame
├── routes/<date>_<time>.csv    taught routes (x, y, yaw_deg, dwell_sec > 0: stop point)
└── backup-<time>/              what a mapping reset archived
```

Site names are `a-z`, `0-9`, `_` and `-` (up to 48). Every path is derived from `sites_dir` and
a site name, never taken from a request. Maps are written crash safe (temporary directory, fsync,
rename; a torn pair is refused on load and the `.bak` pair is used).

## Nodes

| Node                  | Role                                                                                   |
| --------------------- | -------------------------------------------------------------------------------------- |
| `site_manager_node`   | the active site, the only publisher of `/map`; loads the site's tags into localization |
| `grid_mapper_node`    | log-odds occupancy grid of one site from `/cloud_registered_body` while mapping        |
| `route_recorder_node` | teaches a route: samples `map -> base_link` while localized into the site's `routes/`  |

## Map a new site

```bash
ros2 launch robot_bringup robot.launch.py site:=lobby start_mapping:=true
# or, with the stack running:
ros2 service call /mapping/start dharma_interfaces/srv/StartMapping "{site: lobby, reset: false}"
```

Drive the robot slowly through the site (REMOTE mode), then:

```bash
ros2 service call /mapping/save std_srvs/srv/Trigger
ros2 service call /mapping/stop std_srvs/srv/Trigger
```

- **Frames.** A new site is mapped in the current map frame, or with the current pose as origin
  when not localized. Continuing a site that has a map or tags needs the robot localized in
  _its_ frame (on one of its tags or by a pose estimate on its map).
- **Scans** between `scan.height_min` and `scan.height_max` above the floor (in the leveled map
  frame, so the band holds while a legged body pitches), minus the footprint.
- **Gates.** Scans taken while `map -> odom` changes are skipped; a pose jump beyond
  `gate.max_jump_m` holds integration until a scan agrees with the map again.
- No loop closure: large sites accumulate error between tags. Put tags along long loops.

## Record the tags

Tags anchor the site's frame. With the map saved and the robot localized, stand in front of each
tag and record it:

```bash
ros2 service call /localization/record_tags std_srvs/srv/Trigger
```

## Teach a route

```bash
ros2 service call /route/start std_srvs/srv/Trigger                  # refused unless LOCALIZED
ros2 service call /route/mark_stop_point dharma_interfaces/srv/MarkStopPoint "{dwell_sec: 5.0}"
ros2 service call /route/stop std_srvs/srv/Trigger                   # route/saved: the path
```

Drive the route; mark stop points where the robot should wait. The Mission panel in RViz has the
same buttons. Load it later with `navigation/load_path` ([Navigation](Navigation.md)).

## Switch sites

```bash
ros2 service call /site/list dharma_interfaces/srv/ListSites
ros2 service call /site/load dharma_interfaces/srv/LoadSite "{site: lobby}"   # resets localization
```

`site/status` reports the site, whether it has a map, the number of tags and routes, and notes
about broken files (never a crash).
