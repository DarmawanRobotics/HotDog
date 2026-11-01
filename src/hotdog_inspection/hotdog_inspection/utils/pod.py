"""
The UniPod MT11 through unipod_driver: the Pod of core.runner on ROS.

Calls block the inspection's worker thread (never an executor callback of their own group).
The two video streams are heavy: they are subscribed only while a point is inspected
(begin() / end()), as the robot's other heavy topics.
"""

from __future__ import annotations

import os
import threading
import time

from hotdog_base.utils.calls import call
from sensor_msgs.msg import Image
from unipod_msgs.msg import GimbalAttitude, GimbalStatus
from unipod_msgs.srv import GetTemperature, Recenter, SetGimbalAngle, SetZoom, ThermalControl

from dharma_utils.ros import SENSOR
from hotdog_inspection.core.config import PodConfig
from hotdog_inspection.core.images import to_bgr, write_jpeg
from hotdog_inspection.core.runner import Pod
from hotdog_inspection.core.thermal import Reading

ZOOM_TOLERANCE = 0.05


class PodClient(Pod):
    """Pan, tilt, zoom, temperatures and snapshots of the pod."""

    def __init__(self, node, config: PodConfig, group):
        self.node = node
        self.config = config
        self.group = group
        ns = config.namespace.rstrip('/')
        self.ns = ns
        self.lock = threading.Lock()
        self.status = (None, 0.0)  # (GimbalStatus, monotonic)
        self.attitude = (None, 0.0)  # (GimbalAttitude, monotonic)
        self.frames = {}  # name -> (Image, monotonic)
        self.image_subs = []

        def client(srv, name):
            return node.create_client(srv, f'{ns}/{name}', callback_group=group)

        self.angle_client = client(SetGimbalAngle, 'set_angle')
        self.zoom_client = client(SetZoom, 'set_zoom')
        self.thermal_client = client(ThermalControl, 'thermal_control')
        self.temperature_client = client(GetTemperature, 'get_temperature')
        self.recenter_client = client(Recenter, 'recenter')
        node.create_subscription(GimbalStatus, f'{ns}/status', self.on_status, 10,
                                 callback_group=group)  # fmt: skip
        node.create_subscription(GimbalAttitude, f'{ns}/attitude', self.on_attitude, SENSOR,
                                 callback_group=group)  # fmt: skip

    # ---------------------------------------------------------------- state
    def on_status(self, msg: GimbalStatus):
        """Keep the pod's status."""
        with self.lock:
            self.status = (msg, time.monotonic())

    def on_attitude(self, msg: GimbalAttitude):
        """Keep the gimbal attitude."""
        with self.lock:
            self.attitude = (msg, time.monotonic())

    def connected(self) -> bool:
        """Return True while the driver reports a connected pod."""
        with self.lock:
            msg, at = self.status
        return msg is not None and bool(msg.connected) and time.monotonic() - at < 5.0

    def pose(self, max_age: float = 2.0) -> tuple[float, float, float] | None:
        """Return the current (pan, tilt, zoom), None when unknown or stale."""
        with self.lock:
            attitude, at = self.attitude
            status, st = self.status
        now = time.monotonic()
        if attitude is None or status is None or now - at > max_age or now - st > 5.0:
            return None
        return float(attitude.yaw), float(attitude.pitch), float(status.zoom)

    # ---------------------------------------------------------------- commands
    def point(self, pan_deg: float, tilt_deg: float, zoom: float) -> str:
        """Point and zoom; '' or the error."""
        timeout = self.config.call_timeout_sec
        res, error = call(self.angle_client, SetGimbalAngle.Request(yaw=pan_deg, pitch=tilt_deg),
                          timeout)  # fmt: skip
        if res is None or not res.success:
            return error or f'set_angle refused: {res.message}'
        current = self.pose()
        if current is not None and abs(current[2] - zoom) < ZOOM_TOLERANCE:
            return ''
        res, error = call(self.zoom_client, SetZoom.Request(zoom=float(zoom)), timeout)
        if res is None or not res.success:
            return error or f'set_zoom refused: {res.message}'
        return ''

    def refresh_shutter(self) -> str:
        """Flat-field correction now."""
        request = ThermalControl.Request(command=ThermalControl.Request.REFRESH_SHUTTER)
        res, error = call(self.thermal_client, request, self.config.call_timeout_sec)
        return '' if res is not None and res.success else error or res.message

    def measure(self, box) -> tuple[Reading | None, str]:
        """Return the temperatures of a box (thermal pixels) or of the frame (None)."""
        request = GetTemperature.Request()
        if box is None:
            request.mode = GetTemperature.Request.FRAME
        else:
            request.mode = GetTemperature.Request.REGION
            request.x, request.y, request.x2, request.y2 = (int(v) for v in box)
        res, error = call(self.temperature_client, request, self.config.call_timeout_sec)
        if res is None or not res.success:
            return None, error or res.message
        d = res.data
        return Reading('', float(d.temp_max), float(d.temp_min), int(d.max_x), int(d.max_y)), ''

    def recenter(self) -> str:
        """Point the pod back to its centre."""
        request = Recenter.Request(mode=Recenter.Request.CENTER)
        res, error = call(self.recenter_client, request, self.config.call_timeout_sec)
        return '' if res is not None and res.success else error or res.message

    # ---------------------------------------------------------------- images
    def begin(self):
        """Subscribe to both video streams for one inspection point."""
        self.end()
        for name, topic in (('thermal', self.config.thermal_image),
                            ('visible', self.config.visible_image)):  # fmt: skip
            self.image_subs.append(self.node.create_subscription(
                Image, f'{self.ns}/{topic}', lambda m, n=name: self.on_image(n, m), SENSOR,
                callback_group=self.group))  # fmt: skip

    def end(self):
        """Stop receiving the video streams."""
        for sub in self.image_subs:
            self.node.destroy_subscription(sub)
        self.image_subs = []
        with self.lock:
            self.frames = {}

    def on_image(self, name: str, msg: Image):
        """Keep the latest frame of a stream."""
        with self.lock:
            self.frames[name] = (msg, time.monotonic())

    def snapshot(self, prefix: str) -> list[str]:
        """Save a frame of each stream newer than now as <prefix>_thermal.jpg and _visible.jpg."""
        since = time.monotonic()
        files = []
        for name in ('thermal', 'visible'):
            msg = self.wait_frame(name, since)
            if msg is None:
                self.node.log.warning('no image for the evidence', stream=name, throttle=10.0)
                continue
            img = to_bgr(msg.encoding, msg.height, msg.width, msg.step, msg.data)
            path = f'{prefix}_{name}.jpg'
            if img is not None and write_jpeg(path, img, self.config.jpeg_quality):
                files.append(os.path.abspath(path))
        return files

    def wait_frame(self, name: str, since: float) -> Image | None:
        """Return the first frame of a stream received after since, None after the timeout."""
        end = time.monotonic() + self.config.image_timeout_sec
        while time.monotonic() < end:
            with self.lock:
                msg, at = self.frames.get(name, (None, 0.0))
            if msg is not None and at >= since:
                return msg
            time.sleep(0.05)
        return None
