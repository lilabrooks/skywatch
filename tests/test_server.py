import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from skywatch import db
from skywatch.cycle import run_cycle
from skywatch.server import make_server
from tests.support import make_config
from tests.test_cycle import clear_fetch

FIXED_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


class ServerTestBase(unittest.TestCase):
    db_path = ":memory:"

    @classmethod
    def setUpClass(cls):
        cls.server = make_server(make_config(port=0, db_path=cls.db_path))
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def get(self, path):
        return urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5)

    def get_text(self, path):
        with self.get(path) as response:
            return response.status, response.headers["Content-Type"], response.read().decode()


class RouteTests(ServerTestBase):
    def test_healthz_returns_ok_json(self):
        with self.get("/healthz") as response:
            self.assertEqual(response.status, 200)
            self.assertIn("application/json", response.headers["Content-Type"])
            self.assertEqual(json.loads(response.read()), {"status": "ok"})

    def test_root_serves_empty_state_page(self):
        # db_path is :memory:, so every request sees a fresh empty schema.
        status, content_type, body = self.get_text("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Skywatch", body)
        self.assertIn("No data yet", body)
        self.assertIn("make cycle", body)

    def test_stylesheet_asset(self):
        status, content_type, body = self.get_text("/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", content_type)
        self.assertIn(".badge.go", body)

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/nope")
        self.assertEqual(ctx.exception.code, 404)


class PopulatedPageTests(unittest.TestCase):
    def test_page_shows_verdicts_after_a_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "skywatch.db")
            conn = db.connect(path)
            run_cycle(conn, make_config(), clear_fetch(), lambda: FIXED_NOW)
            conn.close()
            server = make_server(make_config(port=0, db_path=path))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                    body = response.read().decode()
                self.assertIn("Last cycle", body)
                self.assertIn("badge go", body)
                self.assertIn("clear and high", body)
                self.assertNotIn("No data yet", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_broken_db_path_yields_500_not_traceback(self):
        config = make_config(port=0, db_path="/dev/null/nope/skywatch.db")
        server = make_server(config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5)
            self.assertEqual(ctx.exception.code, 500)
            self.assertNotIn("Traceback", ctx.exception.read().decode())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
