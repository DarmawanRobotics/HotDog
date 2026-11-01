"""
The channels an alert goes out on: Telegram (Bot API) and a JSON webhook.

Plain urllib (the environment's HTTPS_PROXY applies); every send returns (ok, error) and never
raises.
"""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
import uuid

from hotdog_alerts.core.events import Alert

TELEGRAM = 'https://api.telegram.org/bot{token}/{method}'
CAPTION_MAX = 1000  # Telegram allows 1024 characters in a caption
TEXT_MAX = 4000  # and 4096 in a message
PHOTO_MAX = 10 * 1024 * 1024


def telegram_text(alert: Alert) -> str:
    """Return the alert as Telegram HTML: the title in bold, the link last."""
    lines = [f'<b>{html.escape(alert.title)}</b>', *(html.escape(x) for x in alert.lines if x)]
    if alert.link:
        lines.append(html.escape(alert.link))
    return '\n'.join(lines)


def post(url: str, body: bytes, content_type: str, timeout: float, headers=None):
    """POST and return (ok, error)."""
    request = urllib.request.Request(url, data=body, method='POST')
    request.add_header('Content-Type', content_type)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return 200 <= response.status < 300, f'HTTP {response.status}'
    except urllib.error.HTTPError as error:
        detail = error.read()[:200].decode('utf-8', 'replace')
        return False, f'HTTP {error.code}: {detail}'
    except (urllib.error.URLError, OSError, ValueError) as error:
        return False, str(getattr(error, 'reason', error))


def multipart(fields: dict, file_field: str, path: str) -> tuple[bytes, str]:
    """Return a multipart/form-data body with fields and one file, and its content type."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f'{value}\r\n'.encode()
        )
    with open(path, 'rb') as f:
        data = f.read()
    name = os.path.basename(path)
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
        + data
        + b'\r\n'
    )
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


class Telegram:
    """A bot sending to chats."""

    def __init__(self, token: str, timeout: float, base: str = TELEGRAM):
        self.token, self.timeout, self.base = token, timeout, base

    def send(self, chat_id: str, alert: Alert) -> tuple[bool, str]:
        """Send an alert (with its image when it fits in a caption)."""
        text = telegram_text(alert)
        image = alert.image
        fits = len(text) <= CAPTION_MAX
        if fits and image and os.path.isfile(image) and os.path.getsize(image) <= PHOTO_MAX:
            fields = {'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}
            try:
                body, kind = multipart(fields, 'photo', image)
            except OSError as error:
                return False, f'{image}: {error}'
            return post(self.url('sendPhoto'), body, kind, self.timeout)
        payload = {'chat_id': chat_id, 'text': text[:TEXT_MAX], 'parse_mode': 'HTML',
                   'disable_web_page_preview': True}  # fmt: skip
        return post(self.url('sendMessage'), json.dumps(payload).encode(), 'application/json',
                    self.timeout)  # fmt: skip

    def url(self, method: str) -> str:
        """Return the Bot API URL of a method."""
        return self.base.format(token=self.token, method=method)


class Webhook:
    """A JSON POST per alert."""

    def __init__(self, url: str, token: str, timeout: float):
        self.url, self.token, self.timeout = url, token, timeout

    def send(self, alert: Alert, robot: str) -> tuple[bool, str]:
        """POST the alert as JSON."""
        payload = {
            'robot': robot,
            'kind': alert.kind,
            'severity': alert.severity,
            'title': alert.title,
            'text': alert.text(),
            'link': alert.link,
            'image': alert.image,
            'data': alert.data,
        }
        headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}
        body = json.dumps(payload, default=str).encode()
        return post(self.url, body, 'application/json', self.timeout, headers)
