"""The README's guaranteed-digest demo, end to end against the capture sink."""

import subprocess
import sys
import unittest
from pathlib import Path

from tests.smtp_capture import SMTPCaptureServer

REPO_ROOT = Path(__file__).resolve().parent.parent


class DemoDigestTests(unittest.TestCase):
    def test_demo_delivers_exactly_one_digest_to_the_sink(self):
        with SMTPCaptureServer() as capture:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/demo_digest.py",
                    "--smtp-port", str(capture.port),
                    "--to", "demo@example.org",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("digest sent:", completed.stdout)
            self.assertEqual(len(capture.messages), 1)
            message = capture.messages[0].message
            self.assertIn("ISS tonight", message["Subject"])
            self.assertEqual(message["To"], "demo@example.org")

    def test_demo_fails_helpfully_without_a_sink(self):
        import socket

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            closed_port = sock.getsockname()[1]
        completed = subprocess.run(
            [sys.executable, "scripts/demo_digest.py", "--smtp-port", str(closed_port)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("mailpit", completed.stderr)


if __name__ == "__main__":
    unittest.main()
