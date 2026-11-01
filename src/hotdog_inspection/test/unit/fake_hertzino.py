"""A stand-in HZ-FA-371 for the tests: login, settings, detections that become records, files."""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from urllib.parse import urlparse

TOKEN = 'token-1'


class Camera:
    """The camera's state."""

    def __init__(self, password='123456', status=2, mode=1):
        self.password = hashlib.md5((password + 'lfxs').encode()).hexdigest()
        self.status = status  # status bits of the next records: 2 corona
        self.mode = mode
        self.duration = 3
        self.detecting = False
        self.started = 0.0
        self.records = [{'id': 7, 'status': 8, 'soundmap_intensity': 99}]  # an old one
        self.expire_token = False
        self.lock = threading.Lock()
        self.calls = []

    def tick(self):
        """While detecting, one new record per detection time."""
        if self.detecting and time.monotonic() - self.started >= self.duration:
            n = max(r['id'] for r in self.records) + 1
            self.records.append({
                'id': n, 'detect_mode': self.mode, 'status': self.status,
                'soundmap_intensity': 42, 'noise_prob': 0.1, 'corona_prob': 0.8,
                'surface_prob': 0.05, 'floating_prob': 0.05, 'saving_path': f'2026110{n}',
                'soundmap_photo_name': 'sm.jpg', 'prpd_photo_name': 'prpd.jpg',
            })  # fmt: skip
            self.started = time.monotonic()


def answers(camera: Camera, method: str, path: str, body: dict):
    """Return (status, JSON answer or bytes) of an authorized request."""
    c = camera
    if path == '/system':
        if method == 'PUT':
            c.duration = int(body.get('detect_times', c.duration))
        return 200, {'work_mode': c.mode, 'detect_times': c.duration}
    if path == '/detect_status':
        return 200, {'detect_status': int(c.detecting)}
    if path in ('/turn_on_detect', '/turn_off_detect'):
        c.detecting, c.started = path == '/turn_on_detect', time.monotonic()
        return 200, {'code': 0}
    if path == '/detect_logs':
        logs = sorted(c.records, key=lambda r: -r['id'])
        return 200, {'logs': logs, 'logs_count': len(logs)}
    if path.startswith('/detect_file/'):
        return 200, b'\xff\xd8' + path.encode()
    return 404, {}


def handler(camera: Camera):
    """Return the request handler class of a camera."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def answer(self, code, data):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def route(self, method):
            path = urlparse(self.path).path
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
            with camera.lock:
                camera.calls.append((method, path))
                camera.tick()
                if path == '/login':
                    ok = body.get('password') == camera.password
                    return self.answer(*((200, {'token': TOKEN}) if ok else (401, {})))
                authorized = self.headers.get('Authorization') == f'Bearer {TOKEN}'
                if camera.expire_token or not authorized:
                    camera.expire_token = False
                    return self.answer(401, {})
                return self.answer(*answers(camera, method, path, body))

        def do_GET(self):
            self.route('GET')

        def do_POST(self):
            self.route('POST')

        def do_PUT(self):
            self.route('PUT')

    return Handler


class FakeHertzino:
    """The camera on 127.0.0.1, port chosen by the system."""

    def __init__(self, camera: Camera | None = None):
        self.camera = camera or Camera()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.camera))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
