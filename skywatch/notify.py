"""SMTP notifier (transport layers and gating: docs/specs/verdict-digest.md).

The cycle depends only on the send(subject, body) shape, so tests swap in a
capturing fake; SMTPNotifier is the real transport, built from SmtpConfig.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from skywatch.config import Config, SmtpConfig

SEND_TIMEOUT = 10.0


class NotifyError(Exception):
    """The SMTP transport failed; the cycle records this and carries on."""


class Notifier(Protocol):
    def send(self, subject: str, body: str) -> None: ...


class SMTPNotifier:
    def __init__(self, smtp: SmtpConfig):
        self.smtp = smtp

    def send(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.smtp.sender
        message["To"] = self.smtp.recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self.smtp.host, self.smtp.port, timeout=SEND_TIMEOUT) as client:
                if self.smtp.starttls:
                    client.starttls()
                if self.smtp.user is not None and self.smtp.password is not None:
                    client.login(self.smtp.user, self.smtp.password)
                client.send_message(message)
        except (smtplib.SMTPException, OSError) as err:
            raise NotifyError(
                f"SMTP send via {self.smtp.host}:{self.smtp.port} failed: {err}"
            ) from err


def build_notifier(config: Config) -> SMTPNotifier | None:
    """The real notifier when SMTP is configured, else None (digest disabled)."""
    return SMTPNotifier(config.smtp) if config.smtp is not None else None
