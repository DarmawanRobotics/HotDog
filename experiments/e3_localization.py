"""
E3: localization error under seeded odometry drift, three estimators on the same runs.

The follower drives three laps of the mall_loop route of dharma_sim (true pose, full rig) with
the odometry drift of dharma_sim's drift scenario. Four tags hang at the corridor ends. On
every run the same odometry, detections (5 Hz, 5 % outliers) and scans feed: hard replacement
by every tag (the v0.1 rule, common.baseline), the gated EKF of dharma_localization with tags,
and the EKF with tags and scan matching (1 Hz) on the site map dharma_sim draws from the
world (the map the stack gets in simulation). Errors are
sampled at 10 Hz against the true pose.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import sys

import common  # noqa: F401  (puts the stack on sys.path)
from common.baseline import HardReplace
from common.metrics import write_rows
from common.navigation import FollowerDriver, follower_config
from common.rig import Rig
from common.tags import Camera, TagDetector
from common.worlds import SEEDS, robot, sim_file
import numpy as np
import yaml

from dharma_localization.core.config import EstimatorConfig, TagConfig
from dharma_localization.core.estimator import MapOdomEstimator
from dharma_localization.core.localizer import Localizer
from dharma_localization.core.sources.base import Measurement
from dharma_localization.core.sources.scan_match import ScanMatchSource, match_config
from dharma_sim.core.config import SimConfig
from dharma_sim.core.lidar import LidarModel
from dharma_sim.core.scenario import load_scenario
from dharma_sim.core.site_fixture import OCCUPIED, rasterize
from dharma_sim.core.world import World
from dharma_utils.io import read_route
from dharma_utils.math import Pose2D, angle_diff, default_rng

METHODS = ('hard_replace', 'ekf_tags', 'ekf_tags_scan')
TAGS = {
    'tag_east': [6.0, -3.0, 0.8, 180.0],
    'tag_north': [4.5, 4.5, 0.8, -90.0],
    'tag_west': [-6.0, 3.0, 0.8, 0.0],
    'tag_south': [-4.5, -4.5, 0.8, 90.0],
}
LAPS = 3
START_SIGMA = (0.05, 0.05, math.radians(2.0))  # dharma_sim's /initialpose
DETECTOR_RANGE_M = 5.0


@dataclass(frozen=True)
class LocRow:
    """One estimator on one run."""

    method: str
    seed: int
    distance_m: float
    ate_m: float
    max_m: float
    yaw_rmse_deg: float
    final_m: float
    inliers: int
    inliers_rejected: int
    outliers: int
    outliers_rejected: int
    scan_matches: int
    scan_rejected: int


def mall_world() -> World:
    """Return dharma_sim's mall_loop with the four E3 tags."""
    with open(sim_file('config/worlds/mall_loop.yaml'), encoding='utf-8') as f:
        data = yaml.safe_load(f)
    data['tags'] = TAGS
    return World.from_dict(data)


class Estimators:
    """The three estimators fed with the same inputs."""

    def __init__(self, world: World, base_cam: np.ndarray):
        self.base_cam = base_cam
        self.ekf = {m: Localizer(MapOdomEstimator(EstimatorConfig()), TagConfig())
                    for m in METHODS[1:]}  # fmt: skip
        self.tags = TagDetector(world, 0.0, default_rng(0)).tags
        for loc in self.ekf.values():
            loc.tags = dict(self.tags)
        self.hard: HardReplace | None = None
        self.hard_fused: dict[str, float] = {}
        spec, grid = rasterize(world)  # the site map dharma_sim draws for the stack
        self.matcher = ScanMatchSource(match_config(0.3, 6.0, 0.5), 4.0)
        self.matcher.set_map(grid >= OCCUPIED, spec)
        self.counts = {m: {'inliers': 0, 'inliers_rejected': 0, 'outliers': 0,
                           'outliers_rejected': 0, 'scan_matches': 0, 'scan_rejected': 0}
                       for m in METHODS}  # fmt: skip

    def start(self, truth: Pose2D, odom: Pose2D, now: float):
        """Localize every estimator at the true start pose."""
        cov = np.diag(np.square(START_SIGMA))
        for loc in self.ekf.values():
            loc.localize(Measurement(truth, cov, now, 'pose_estimate'), odom, now)
        self.hard = HardReplace(truth, odom)

    def track(self, odom: Pose2D, now: float):
        """Follow odometry."""
        for loc in self.ekf.values():
            loc.track(odom, now)
        self.hard.track(odom)

    def tag(self, detection, odom: Pose2D, now: float):
        """Feed one detection to every estimator (0.5 s per tag, as TagConfig)."""
        kind = 'outliers' if detection.outlier else 'inliers'
        frame, cam_tag = detection.frame, detection.cam_tag
        interval = TagConfig().min_interval_sec
        for method, loc in self.ekf.items():
            m = loc.measure_tag(frame, self.base_cam, cam_tag, now)
            if isinstance(m, str):
                continue
            before = loc.last_fused.get(frame)
            samples = loc.on_tag(m, odom, now)
            if loc.last_fused.get(frame) != before:
                self.counts[method][kind] += 1
                self.counts[method][f'{kind}_rejected'] += not samples
        if now - self.hard_fused.get(frame, -math.inf) >= interval:
            self.hard_fused[frame] = now
            self.counts['hard_replace'][kind] += 1
            accepted = self.hard.on_tag(self.tags[frame], self.base_cam, cam_tag)
            self.counts['hard_replace'][f'{kind}_rejected'] += not accepted

    def scan(self, points_base: np.ndarray, odom: Pose2D, now: float):
        """Match a scan for the scan-matching estimator."""
        loc = self.ekf['ekf_tags_scan']
        prior = loc.estimator.map_odom @ odom
        m = self.matcher.measure(points_base, prior, now)
        if isinstance(m, str):
            return
        result, _ = loc.correct(m, odom, now)
        self.counts['ekf_tags_scan']['scan_matches'] += 1
        self.counts['ekf_tags_scan']['scan_rejected'] += not result.accepted

    def poses(self) -> dict[str, Pose2D]:
        """Return map->base of every estimator."""
        out = {m: loc.estimator.base_pose() for m, loc in self.ekf.items()}
        out['hard_replace'] = self.hard.base_pose()
        return out


def planar_scan(points: np.ndarray, mount, base_height: float) -> np.ndarray:
    """Return the scan in the planar base frame, height band 0.1-1.5 m, up to 15 m."""
    base = points + np.asarray(mount)
    height = base[:, 2] + base_height
    keep = (height >= 0.1) & (height <= 1.5) & (np.hypot(base[:, 0], base[:, 1]) <= 15.0)
    return base[keep, :2]


def run(seed: int, laps: int = LAPS) -> list[LocRow]:
    """Run one seed; return a row per estimator (seed 1 also writes its error series)."""
    world, profile = mall_world(), robot()
    drift = load_scenario(str(sim_file('config/scenarios/drift.yaml')))
    scenario = replace(drift, seed=seed)
    rig = Rig(world, profile, seed, scenario, SimConfig(seed=seed))
    points = read_route(str(sim_file('config/routes/mall_loop.csv')))
    driver = FollowerDriver(rig, points, follower_config(loop_route=True), start_sec=1.0)
    rng = default_rng([seed, 3])
    camera = Camera(max_range=DETECTOR_RANGE_M)
    detector = TagDetector(world, profile.base_height, rng, camera)
    est = Estimators(world, camera.base_cam())
    lidar = LidarModel(rig.sim.config.lidar, profile.base_height, default_rng([seed, 4]))
    errors = {m: [] for m in METHODS}
    series = []
    tick = [0]

    def drive(r: Rig, now: float):
        command = driver(r, now)
        odom, truth = r.sim.odometry.pose, r.pose
        if tick[0] == 0:
            est.start(truth, odom, now)
        est.track(odom, now)
        if tick[0] % 4 == 0:
            for detection in detector.detect(truth):
                est.tag(detection, odom, now)
        if tick[0] % 20 == 10:
            scan = lidar.scan(world, truth, r.sim.obstacles(now))
            est.scan(planar_scan(scan, rig.sim.config.lidar.mount_xyz, profile.base_height),
                     odom, now)  # fmt: skip
        if tick[0] % 2 == 0:
            for method, pose in est.poses().items():
                errors[method].append((math.hypot(pose.x - truth.x, pose.y - truth.y),
                                       angle_diff(pose.yaw, truth.yaw)))  # fmt: skip
            series.append((now, r.sim.odometry.distance, *(errors[m][-1][0] for m in METHODS)))
        tick[0] += 1
        return command

    rig.driver = drive
    rig.run(600.0, lambda r: driver.follower.lap >= laps)
    distance = float(np.sum(np.hypot(*np.diff(rig.trace.arrays()['pose'][:, :2], axis=0).T)))
    if seed == 1 and laps == LAPS:
        header = ('t_sec', 'odom_distance_m', *(f'{m}_error_m' for m in METHODS))
        write_rows('e3_errors_seed1', [dict(zip(header, v)) for v in series])
    rows = []
    for method in METHODS:
        e = np.asarray(errors[method])
        rows.append(LocRow(
            method, seed, distance, float(np.sqrt(np.mean(e[:, 0] ** 2))), float(e[:, 0].max()),
            math.degrees(float(np.sqrt(np.mean(e[:, 1] ** 2)))), float(e[-1, 0]),
            **est.counts[method],
        ))  # fmt: skip
    return rows


def main(seeds=SEEDS) -> list[LocRow]:
    """Run every seed; write results/e3_localization.csv."""
    rows = [row for seed in seeds for row in run(seed)]
    write_rows('e3_localization', rows)
    return rows


if __name__ == '__main__':
    main(SEEDS if len(sys.argv) < 2 else tuple(range(1, int(sys.argv[1]) + 1)))
