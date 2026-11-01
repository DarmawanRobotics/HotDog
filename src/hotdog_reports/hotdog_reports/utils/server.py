"""The reports folder over HTTP, read-only: the pages, the images, the tables, the JSON."""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading


class _Handler(SimpleHTTPRequestHandler):
    """GET and HEAD of the files under the folder; nothing is written or executed."""

    def log_message(self, format, *args):
        """Stay quiet (the node logs the server's start)."""

    def end_headers(self):
        """Never cache: the front page and the day pages change during the day."""
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


class ReportServer:
    """A threaded HTTP server on its own daemon thread."""

    def __init__(self, directory: str, host: str, port: int):
        handler = functools.partial(_Handler, directory=directory)
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        """Return the port listened on (useful with port 0)."""
        return int(self.httpd.server_address[1])

    def start(self):
        """Serve in the background."""
        self.thread.start()

    def stop(self):
        """Stop serving and close the socket."""
        self.httpd.shutdown()
        self.httpd.server_close()
