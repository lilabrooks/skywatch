"""The README's guaranteed-digest demo, end to end against the capture sink."""

import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path

from tests.smtp_capture import SMTPCaptureServer

REPO_ROOT = Path(__file__).resolve().parent.parent


def clean_env(**overrides):
    """The inherited environment minus any SMTP_* the developer's shell has."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMTP_")}
    env.update(overrides)
    return env


def run_demo(*argv, **env_overrides):
    return subprocess.run(
        [sys.executable, "scripts/demo_digest.py", *argv],
        cwd=REPO_ROOT,
        env=clean_env(**env_overrides),
        capture_output=True,
        text=True,
        timeout=30,
    )


def closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class DemoDigestTests(unittest.TestCase):
    def test_demo_delivers_exactly_one_digest_to_the_sink(self):
        with SMTPCaptureServer() as capture:
            completed = run_demo(
                "--smtp-port", str(capture.port), "--to", "demo@example.org"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("digest sent:", completed.stdout)
            self.assertEqual(len(capture.messages), 1)
            message = capture.messages[0].message
            self.assertIn("ISS tonight", message["Subject"])
            self.assertEqual(message["To"], "demo@example.org")

    def test_demo_fails_helpfully_without_a_sink(self):
        completed = run_demo("--smtp-port", str(closed_port()))
        self.assertEqual(completed.returncode, 1)
        self.assertIn("mailpit", completed.stderr)

    def test_env_smtp_port_and_to_are_respected(self):
        with SMTPCaptureServer() as capture:
            completed = run_demo(
                SMTP_PORT=str(capture.port), SMTP_TO="env@example.org"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(len(capture.messages), 1)
            self.assertEqual(capture.messages[0].message["To"], "env@example.org")

    def test_flags_beat_environment(self):
        with SMTPCaptureServer() as capture:
            completed = run_demo(
                "--smtp-port", str(capture.port), "--to", "flag@example.org",
                SMTP_PORT=str(closed_port()), SMTP_TO="env@example.org",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(len(capture.messages), 1)
            self.assertEqual(capture.messages[0].message["To"], "flag@example.org")

    def test_garbage_env_smtp_port_rejected_clearly(self):
        completed = run_demo(SMTP_PORT="banana")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("SMTP_PORT", completed.stderr)
        self.assertIn("'banana'", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
