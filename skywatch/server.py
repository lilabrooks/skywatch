"""Local HTTP server: the status page, a stylesheet, and the health endpoint.

Loopback-only per ADR-0001; page contract in docs/specs/status-page.md. Each
page request opens its own SQLite connection (WAL keeps readers unblocked).
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from skywatch import __version__, db, page
from skywatch.config import Config
from skywatch.model import utcnow

log = logging.getLogger("skywatch.server")


class SkywatchHandler(BaseHTTPRequestHandler):
    server_version = f"Skywatch/{__version__}"

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, "application/json; charset=utf-8", json.dumps({"status": "ok"}))
        elif self.path == "/":
            self._send_status_page()
        elif self.path == "/style.css":
            self._send(200, "text/css; charset=utf-8", page.STYLESHEET)
        else:
            self._send(404, "text/plain; charset=utf-8", "not found\n")

    def _send_status_page(self) -> None:
        config: Config = self.server.config  # type: ignore[attr-defined]
        try:
            conn = db.connect(config.db_path)
            try:
                body = page.render(config, conn, utcnow())
            finally:
                conn.close()
        except Exception:
            log.exception("status page failed to render")
            self._send(
                500,
                "text/plain; charset=utf-8",
                "internal error rendering the status page; see the server log\n",
            )
            return
        self._send(200, "text/html; charset=utf-8", body)

    def _send(self, status: int, content_type: str, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        log.info("%s %s", self.address_string(), format % args)


class SkywatchServer(ThreadingHTTPServer):
    def __init__(self, config: Config):
        super().__init__((config.host, config.port), SkywatchHandler)
        self.config = config


def make_server(config: Config) -> SkywatchServer:
    """Bind and return the server (config.port 0 picks an ephemeral port, for tests)."""
    return SkywatchServer(config)
