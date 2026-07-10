"""Local HTTP server: health endpoint now, status page in a later milestone."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from skywatch import __version__

log = logging.getLogger("skywatch.server")


class SkywatchHandler(BaseHTTPRequestHandler):
    server_version = f"Skywatch/{__version__}"

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, "application/json; charset=utf-8", json.dumps({"status": "ok"}))
        elif self.path == "/":
            body = (
                "<!doctype html>\n<title>Skywatch</title>\n"
                "<p>Skywatch is running. The status page lands in a later milestone.</p>\n"
            )
            self._send(200, "text/html; charset=utf-8", body)
        else:
            self._send(404, "text/plain; charset=utf-8", "not found\n")

    def _send(self, status: int, content_type: str, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        log.info("%s %s", self.address_string(), format % args)


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    """Bind and return the server (port 0 picks an ephemeral port, for tests)."""
    return ThreadingHTTPServer((host, port), SkywatchHandler)
