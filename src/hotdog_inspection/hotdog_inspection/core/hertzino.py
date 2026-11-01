"""
The Hertzinno HZ-FA-371 acoustic camera over its HTTP API (manual V5.1, chapter 5), stdlib only.

The ROS driver of the camera (DarmawanRobotics/hertzino_driver) runs on ROS 1 Noetic; HotDog
runs ROS 2 Foxy, so it talks to the camera directly, with the part of the API a detection
needs: login (token, MD5 password), the detection settings, start / stop, the records and
their photos. A 401 logs in again once.
"""

from __future__ import annotations

import hashlib
import json
import re
from urllib import error as urlerror
from urllib import request as urlrequest

PARTIAL_DISCHARGE = 1
LEAKAGE = 2
PD_TYPES = ((1, 'noise'), (2, 'corona'), (4, 'surface'), (8, 'floating'))
PLAIN_RE = re.compile(r'^[A-Za-z0-9_.-]+$')


class HertzinoError(RuntimeError):
    """The camera is unreachable or refused a request."""


def password_hash(password: str) -> str:
    """Return the login password field: lower-case MD5 of the password followed by 'lfxs'."""
    return hashlib.md5((password + 'lfxs').encode('utf-8')).hexdigest()


def plain(name: str) -> bool:
    """Return True for a file or folder name the camera serves (no path parts)."""
    return bool(PLAIN_RE.match(name)) and name not in ('.', '..')


def types_of(status: int) -> list[str]:
    """Return the partial discharge types of a result's status bits."""
    return [name for bit, name in PD_TYPES if int(status) & bit]


class HertzinoClient:
    """Token login and the JSON requests of the camera."""

    def __init__(self, host: str, port: int, user: str, password: str, timeout: float = 5.0):
        self.base = f'http://{host}:{int(port)}'
        self.user, self.password, self.timeout = user, password, timeout
        self.token = ''

    def login(self):
        """Get a token (POST /login)."""
        body = {'username': self.user, 'password': password_hash(self.password)}
        data = self._send('POST', '/login', body, auth=False)
        token = data.get('token') or data.get('access_token') if isinstance(data, dict) else ''
        if not token:
            raise HertzinoError('login: no token in the answer')
        self.token = str(token)

    def request(self, method: str, path: str, body=None):
        """Return the JSON answer of a request; log in first or again after a 401."""
        if not self.token:
            self.login()
        try:
            return self._send(method, path, body)
        except PermissionError:
            self.login()
            return self._send(method, path, body)

    def raw(self, path: str) -> bytes:
        """Return the bytes of a GET (files); log in again after a 401."""
        if not self.token:
            self.login()
        try:
            return self._open('GET', path, None, True)
        except PermissionError:
            self.login()
            return self._open('GET', path, None, True)

    def _send(self, method: str, path: str, body, auth: bool = True):
        text = self._open(method, path, body, auth).decode('utf-8', 'replace').strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError as error:
            raise HertzinoError(f'{method} {path}: not JSON ({text[:80]!r})') from error

    def _open(self, method: str, path: str, body, auth: bool) -> bytes:
        data = None if body is None else json.dumps(body).encode('utf-8')
        req = urlrequest.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if auth:
            req.add_header('Authorization', f'Bearer {self.token}')
        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as answer:
                return answer.read()
        except urlerror.HTTPError as error:
            if error.code == 401 and auth:
                raise PermissionError(path) from error
            raise HertzinoError(f'{method} {path}: HTTP {error.code}') from error
        except (urlerror.URLError, OSError) as error:
            raise HertzinoError(f'{method} {path}: {error}') from error

    # ---------------------------------------------------------------- API
    def system(self) -> dict:
        """Return the detection settings (work_mode, dB_limit, band, detect_times, ...)."""
        data = self.request('GET', '/system')
        if not isinstance(data, dict):
            raise HertzinoError('/system: unexpected answer')
        return data

    def set_duration(self, seconds: int):
        """Set the detection time (1..3600 s)."""
        if not 1 <= int(seconds) <= 3600:
            raise HertzinoError(f'detection time {seconds} s outside 1..3600')
        self.request('PUT', '/system', {'detect_times': int(seconds)})

    def detecting(self) -> bool:
        """Return True while a detection runs (GET /detect_status)."""
        data = self.request('GET', '/detect_status')
        return bool(int(data.get('detect_status', 0))) if isinstance(data, dict) else False

    def start(self):
        """Start detecting (POST /turn_on_detect); results become records."""
        self.request('POST', '/turn_on_detect')

    def stop(self):
        """Stop detecting (POST /turn_off_detect)."""
        self.request('POST', '/turn_off_detect')

    def records(self, mode: int = PARTIAL_DISCHARGE, count: int = 20) -> list[dict]:
        """Return the newest records of a mode (the camera keeps the latest 100)."""
        types = 3 if mode == LEAKAGE else 15
        query = (f'start_col=1&col_count={int(count)}&start_time=0&end_time=2000000000'
                 f'&discharge_type={types}&detect_mode={int(mode)}')  # fmt: skip
        path = f'/detect_logs?{query}'
        data = self.request('GET', path)
        logs = data.get('logs') if isinstance(data, dict) else None
        return [r for r in logs or [] if isinstance(r, dict)]

    def file(self, saving_path: str, name: str) -> bytes:
        """Return a photo or video of a record (GET /detect_file/<saving_path>/<name>)."""
        folder = saving_path.strip('/')
        if not (plain(folder) and plain(name)):
            raise HertzinoError(f'not a plain file name: {saving_path!r} / {name!r}')
        return self.raw(f'/detect_file/{folder}/{name}')


def record_id(record: dict) -> int:
    """Return the id of a record (-1 when it has none)."""
    try:
        return int(record.get('id', record.get('log_id', -1)))
    except (TypeError, ValueError):
        return -1
