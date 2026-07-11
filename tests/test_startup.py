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


def run_skywatch(env_overrides, cwd=REPO_ROOT, **kwargs):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(REPO_ROOT),
        "SKYWATCH_ENV_FILE": "",  # hermetic: a developer's .env must not leak in
        **env_overrides,
    }
    return subprocess.Popen(
        [sys.executable, "-m", "skywatch"],
        cwd=cwd,
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


class EnvFileTests(unittest.TestCase):
    """Precedence at process level: already-set environment beats .env."""

    def finish(self, process):
        _, stderr = process.communicate(timeout=10)
        return process.returncode, stderr

    def test_environment_wins_over_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text("LATITUDE=banana\nLONGITUDE=-122.33\n")
            process = run_skywatch(
                {
                    "LATITUDE": "not-a-number-either",
                    "SKYWATCH_ENV_FILE": ".env",
                },
                cwd=tmp,
            )
            code, stderr = self.finish(process)
            self.assertEqual(code, 2)
            self.assertIn("'not-a-number-either'", stderr, "the environment value must win")
            self.assertNotIn("'banana'", stderr)

    def test_env_file_fills_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text("LATITUDE=banana\n")
            process = run_skywatch({"SKYWATCH_ENV_FILE": ".env"}, cwd=tmp)
            code, stderr = self.finish(process)
            self.assertEqual(code, 2)
            self.assertIn("'banana'", stderr, "file value applies when the env has none")
            self.assertIn("LONGITUDE", stderr)

    def test_empty_skywatch_env_file_disables_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text("LATITUDE=banana\nLONGITUDE=-122.33\n")
            process = run_skywatch({}, cwd=tmp)  # SKYWATCH_ENV_FILE="" by default here
            code, stderr = self.finish(process)
            self.assertEqual(code, 2)
            self.assertNotIn("banana", stderr)
            self.assertIn("LATITUDE", stderr)  # reported missing, not garbage

    def test_blank_environment_value_is_filled_from_env_file(self):
        # Reproduces the reported symptom: LATITUDE exported empty in the shell,
        # a valid .env copied from the example, yet startup said "not set".
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text("LATITUDE=47.61\nLONGITUDE=-122.33\n")
            port = free_port()
            process = run_skywatch(
                {
                    "LATITUDE": "",  # shadowing empty value
                    "SKYWATCH_ENV_FILE": ".env",
                    "PORT": str(port),
                    "DB_PATH": f"{tmp}/skywatch.db",
                    "PASSES_BASE_URL": f"http://127.0.0.1:{free_port()}/p",
                    "FORECAST_BASE_URL": f"http://127.0.0.1:{free_port()}/f",
                },
                cwd=tmp,
            )
            try:
                serving = False
                for _ in range(50):
                    line = process.stderr.readline()
                    if not line or f"serving on http://127.0.0.1:{port}" in line:
                        serving = bool(line)
                        break
                self.assertTrue(serving, "blank env var must not block the .env value")
            finally:
                process.terminate()
                process.communicate(timeout=10)

    def test_missing_env_file_hint_points_at_the_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No .env here, and none of the required vars in the environment.
            process = run_skywatch({"SKYWATCH_ENV_FILE": ".env"}, cwd=tmp)
            code, stderr = self.finish(process)
            self.assertEqual(code, 2)
            self.assertIn("cp .env.example .env", stderr)
            self.assertIn("no .env file found", stderr)


class PortInUseTests(unittest.TestCase):
    def test_taken_port_fails_fast_with_clear_message(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            taken = sock.getsockname()[1]
            with tempfile.TemporaryDirectory() as tmp:
                process = run_skywatch(
                    {
                        "LATITUDE": "47.61",
                        "LONGITUDE": "-122.33",
                        "PORT": str(taken),
                        "DB_PATH": f"{tmp}/skywatch.db",
                    }
                )
                _, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 2)
        self.assertIn("cannot bind", stderr)
        self.assertIn(str(taken), stderr)
        self.assertIn("PORT", stderr)
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
