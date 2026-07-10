import json
import threading
import unittest
import urllib.error
import urllib.request

from skywatch.server import make_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)  # ephemeral port
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

    def test_healthz_returns_ok_json(self):
        with self.get("/healthz") as response:
            self.assertEqual(response.status, 200)
            self.assertIn("application/json", response.headers["Content-Type"])
            self.assertEqual(json.loads(response.read()), {"status": "ok"})

    def test_root_serves_placeholder_page(self):
        with self.get("/") as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
            self.assertIn("Skywatch", response.read().decode("utf-8"))

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/nope")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
