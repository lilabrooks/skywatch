"""End-to-end startup behavior of `python3 -m skywatch` (the `make run` contract)."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_skywatch(env_overrides, **kwargs):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONUNBUFFERED": "1",
        **env_overrides,
    }
    return subprocess.Popen(
        [sys.executable, "-m", "skywatch"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )


class StartupFailureTests(unittest.TestCase):
    def finish(self, process):
        try:
            _, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            self.fail("skywatch did not exit promptly on bad configuration")
        return process.returncode, stderr

    def test_garbage_latitude_fails_fast_naming_expected_format(self):
        process = run_skywatch(
            {"LATITUDE": "banana", "LONGITUDE": "-122.33"}
        )
        code, stderr = self.finish(process)
        self.assertEqual(code, 2)
        self.assertIn("LATITUDE", stderr)
        self.assertIn("decimal degrees between -90 and 90", stderr)
        self.assertIn("'banana'", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_missing_configuration_reports_every_variable(self):
        process = run_skywatch({})
        code, stderr = self.finish(process)
        self.assertEqual(code, 2)
        self.assertIn("LATITUDE", stderr)
        self.assertIn("LONGITUDE", stderr)
        self.assertNotIn("Traceback", stderr)


class StartupSuccessTests(unittest.TestCase):
    def test_boots_and_serves_healthz(self):
        port = free_port()
        closed = free_port()  # nothing listens: the boot cycle fails fast, offline
        with tempfile.TemporaryDirectory() as tmp:
            self._boot_and_check(port, closed, tmp)

    def _boot_and_check(self, port, closed, tmp):
        process = run_skywatch(
            {
                "LATITUDE": "47.61",
                "LONGITUDE": "-122.33",
                "PORT": str(port),
                "DB_PATH": f"{tmp}/skywatch.db",
                # Serve mode runs a cycle immediately; keep it off the network.
                "PASSES_BASE_URL": f"http://127.0.0.1:{closed}/passes",
                "FORECAST_BASE_URL": f"http://127.0.0.1:{closed}/forecast",
            }
        )
        try:
            # The entrypoint logs the bound address once it is serving.
            serving = False
            for _ in range(50):
                line = process.stderr.readline()
                if not line:
                    break
                if f"serving on http://127.0.0.1:{port}" in line:
                    serving = True
                    break
            self.assertTrue(serving, "server never reported its address")
            url = f"http://127.0.0.1:{port}/healthz"
            with urllib.request.urlopen(url, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read()), {"status": "ok"})
        finally:
            process.terminate()
            process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
