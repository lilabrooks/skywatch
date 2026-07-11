"""SMTPNotifier over a real loopback socket against the capture server."""

import socket
import unittest

from skywatch.config import SmtpConfig
from skywatch.notify import NotifyError, SMTPNotifier
from tests.smtp_capture import SMTPCaptureServer


class SMTPNotifierTests(unittest.TestCase):
    def test_sends_one_wellformed_message(self):
        with SMTPCaptureServer() as capture:
            smtp = SmtpConfig(
                host="127.0.0.1",
                port=capture.port,
                sender="skywatch@localhost",
                recipient="owner@example.org",
            )
            SMTPNotifier(smtp).send("ISS tonight: test", "body line 1\nline 2\n.dot line")
            self.assertEqual(len(capture.messages), 1)
            captured = capture.messages[0]
            self.assertEqual(captured.mail_from, "skywatch@localhost")
            self.assertEqual(captured.rcpt_tos, ["owner@example.org"])
            message = captured.message
            self.assertEqual(message["Subject"], "ISS tonight: test")
            self.assertEqual(message["From"], "skywatch@localhost")
            self.assertEqual(message["To"], "owner@example.org")
            self.assertIn("line 2", message.get_content())
            self.assertIn(".dot line", message.get_content(), "dot-stuffing must round-trip")

    def test_unreachable_server_raises_notify_error(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            closed_port = sock.getsockname()[1]
        smtp = SmtpConfig(
            host="127.0.0.1", port=closed_port, sender="a@b", recipient="c@d"
        )
        with self.assertRaises(NotifyError) as ctx:
            SMTPNotifier(smtp).send("s", "b")
        self.assertIn("SMTP send", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
