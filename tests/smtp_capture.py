"""Minimal loopback SMTP capture server for tests (stdlib smtpd was removed
in Python 3.12; ADR-0001 hand-rolls this instead of depending on aiosmtpd).

Speaks just enough ESMTP for smtplib.send_message: EHLO/HELO, MAIL, RCPT,
DATA (with dot-unstuffing), RSET, NOOP, QUIT. No TLS, no auth — it exists to
capture what a real SMTP client sends over a real local socket.
"""

from __future__ import annotations

import email.parser
import email.policy
import socketserver
import threading
from dataclasses import dataclass


@dataclass
class CapturedMessage:
    mail_from: str
    rcpt_tos: list[str]
    data: bytes

    @property
    def message(self):
        return email.parser.BytesParser(policy=email.policy.default).parsebytes(self.data)


def _address(line: bytes) -> str:
    text = line.decode("utf-8", "replace")
    if "<" in text and ">" in text:
        return text[text.index("<") + 1 : text.index(">")]
    return text.split(":", 1)[-1].strip()


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 skywatch-capture ESMTP\r\n")
        mail_from, rcpt_tos = "", []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            command = line.strip().upper()
            if command.startswith(b"EHLO") or command.startswith(b"HELO"):
                self.wfile.write(b"250 skywatch-capture\r\n")
            elif command.startswith(b"MAIL"):
                mail_from = _address(line)
                self.wfile.write(b"250 OK\r\n")
            elif command.startswith(b"RCPT"):
                rcpt_tos.append(_address(line))
                self.wfile.write(b"250 OK\r\n")
            elif command.startswith(b"DATA"):
                self.wfile.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                chunks = []
                while True:
                    data_line = self.rfile.readline()
                    if not data_line or data_line == b".\r\n":
                        break
                    if data_line.startswith(b".."):
                        data_line = data_line[1:]
                    chunks.append(data_line)
                self.server.deliver(  # type: ignore[attr-defined]
                    CapturedMessage(mail_from, list(rcpt_tos), b"".join(chunks))
                )
                mail_from, rcpt_tos = "", []
                self.wfile.write(b"250 OK: captured\r\n")
            elif command.startswith(b"RSET") or command.startswith(b"NOOP"):
                mail_from, rcpt_tos = "", []
                self.wfile.write(b"250 OK\r\n")
            elif command.startswith(b"QUIT"):
                self.wfile.write(b"221 Bye\r\n")
                return
            else:
                self.wfile.write(b"502 command not implemented\r\n")


class SMTPCaptureServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self._lock = threading.Lock()
        self.messages: list[CapturedMessage] = []
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    def deliver(self, message: CapturedMessage) -> None:
        with self._lock:
            self.messages.append(message)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def __enter__(self) -> "SMTPCaptureServer":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)


def _main() -> None:
    """Standalone local mail sink for manual checks: prints captured mail.

    Usage: python3 -m tests.smtp_capture [port]   (default 2525)
    """
    import sys
    import time

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2525

    class FixedPortServer(SMTPCaptureServer):
        def __init__(self):
            socketserver.ThreadingTCPServer.__init__(self, ("127.0.0.1", port), _Handler)
            self._lock = threading.Lock()
            self.messages = []
            self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    with FixedPortServer() as sink:
        print(f"capture sink listening on 127.0.0.1:{sink.port} (Ctrl-C to stop)", flush=True)
        seen = 0
        try:
            while True:
                time.sleep(0.2)
                while seen < len(sink.messages):
                    message = sink.messages[seen].message
                    seen += 1
                    print(
                        f"--- captured #{seen} ---\n"
                        f"From: {message['From']}\nTo: {message['To']}\n"
                        f"Subject: {message['Subject']}\n\n{message.get_content()}",
                        flush=True,
                    )
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    _main()
