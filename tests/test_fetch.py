"""FetchError mapping, exercised against a real local HTTP server (offline)."""

import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from skywatch.fetch import FetchError, http_get_json


class FakeUpstreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/ok":
                body = b'{"answer": 42}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/http500":
                self.send_error(500, "boom")
            elif self.path == "/garbage":
                body = b"<html>not json</html>"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/slow":
                time.sleep(0.5)
                self.send_error(504)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client gave up (the timeout test); nothing to do

    def log_message(self, format, *args):
        pass


class SilentServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # expected disconnects from the timeout test


class HttpGetJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = SilentServer(("127.0.0.1", 0), FakeUpstreamHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_ok_json(self):
        self.assertEqual(http_get_json(f"{self.base}/ok", timeout=5), {"answer": 42})

    def test_http_error_status(self):
        with self.assertRaises(FetchError) as ctx:
            http_get_json(f"{self.base}/http500", timeout=5)
        self.assertIn("HTTP 500", str(ctx.exception))

    def test_non_json_body(self):
        with self.assertRaises(FetchError) as ctx:
            http_get_json(f"{self.base}/garbage", timeout=5)
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_timeout(self):
        with self.assertRaises(FetchError) as ctx:
            http_get_json(f"{self.base}/slow", timeout=0.1)
        self.assertIn("timed out", str(ctx.exception))

    def test_connection_refused(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            closed_port = sock.getsockname()[1]
        with self.assertRaises(FetchError) as ctx:
            http_get_json(f"http://127.0.0.1:{closed_port}/ok", timeout=2)
        self.assertIn("cannot reach", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
