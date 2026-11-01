"""A stand-in for the Telegram Bot API and a webhook, on 127.0.0.1, recording every request."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


class FakeApi:
    """POST /bot<token>/sendMessage | sendPhoto, POST /hook; status per path."""

    def __init__(self):
        self.requests: list[dict] = []
        self.status = 200
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                kind = self.headers.get('Content-Type', '')
                entry = {'path': self.path, 'type': kind, 'body': body,
                         'auth': self.headers.get('Authorization', '')}  # fmt: skip
                if kind.startswith('application/json'):
                    entry['json'] = json.loads(body)
                api.requests.append(entry)
                self.send_response(api.status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ok': api.status == 200}).encode())

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        """Return http://127.0.0.1:<port>."""
        return f'http://127.0.0.1:{self.httpd.server_address[1]}'

    def stop(self):
        """Stop the server."""
        self.httpd.shutdown()
        self.httpd.server_close()
