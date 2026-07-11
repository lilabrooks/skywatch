#!/usr/bin/env python3
"""Send one guaranteed Skywatch digest through a local mail sink.

Recorded upstream fixtures are time-shifted so "tonight" has clear-sky
visible passes, served from a loopback HTTP server, and one real cycle runs
against them — so the digest goes out regardless of actual weather. Nothing
leaves the machine: the SMTP target is a local sink.

Start an inbox first, either:
    mailpit                              # UI at http://localhost:8025
    python3 -m tests.smtp_capture 1025   # repo sink, prints to stdout

Then:  make demo   (or: python3 scripts/demo_digest.py [--to you@example.org])
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skywatch.config import Config, SmtpConfig  # noqa: E402
from skywatch.cycle import CycleRunner  # noqa: E402
from skywatch.model import parse_utc  # noqa: E402
from skywatch.notify import SMTPNotifier  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def shifted_passes(now: datetime) -> list:
    passes = json.loads((FIXTURES / "terrestre_passes.json").read_text())
    first_visible = next(p for p in passes if p["visible"])
    anchor = parse_utc(first_visible["rise"]["utc_datetime"])
    delta = (now + timedelta(hours=2)) - anchor  # first visible pass: ~2h away
    for p in passes:
        for event in ("rise", "culmination", "set"):
            moment = parse_utc(p[event]["utc_datetime"]) + delta
            p[event]["utc_datetime"] = moment.strftime("%Y-%m-%d %H:%M:%S+00:00")
            p[event]["utc_timestamp"] = int(moment.timestamp())
    return passes


def clear_forecast(now: datetime) -> dict:
    base = now.replace(minute=0, second=0, microsecond=0)
    hours = [base + timedelta(hours=i) for i in range(48)]
    return {
        "hourly": {
            "time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
            "cloud_cover": [5] * len(hours),
        }
    }


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def serve_fixtures(directory: str) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--to", default=None,
        help="digest recipient (default: $SMTP_TO, else you@example.org)",
    )
    parser.add_argument(
        "--smtp-port", type=int, default=None,
        help="local sink port (default: $SMTP_PORT, else 1025); the host is "
        "always 127.0.0.1 — the demo never sends off-machine",
    )
    args = parser.parse_args()

    recipient = args.to or os.environ.get("SMTP_TO", "").strip() or "you@example.org"
    smtp_port = args.smtp_port
    if smtp_port is None:
        raw = os.environ.get("SMTP_PORT", "").strip()
        try:
            smtp_port = int(raw) if raw else 1025
        except ValueError:
            print(f"demo: SMTP_PORT must be a port number, got {raw!r}", file=sys.stderr)
            return 2

    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "passes.json").write_text(json.dumps(shifted_passes(now)))
        (Path(tmp) / "forecast.json").write_text(json.dumps(clear_forecast(now)))
        server, port = serve_fixtures(tmp)
        smtp = SmtpConfig(
            host="127.0.0.1", port=smtp_port,
            sender="skywatch@localhost", recipient=recipient,
        )
        config = Config(
            latitude=47.61, longitude=-122.33, port=0,
            db_path=str(Path(tmp) / "demo.db"),
            smtp=smtp,
            passes_base_url=f"http://127.0.0.1:{port}/passes.json",
            forecast_base_url=f"http://127.0.0.1:{port}/forecast.json",
        )
        try:
            result = CycleRunner(config, notifier=SMTPNotifier(smtp)).run()
        finally:
            server.shutdown()
            server.server_close()

    print(
        f"cycle: passes {result.passes_status} | forecast {result.forecast_status} "
        f"| digest {result.digest_status}"
    )
    if result.digest_status.startswith("sent:"):
        print(f"Delivered to the sink on 127.0.0.1:{smtp_port} — check your inbox UI.")
        return 0
    if result.digest_status.startswith("error:"):
        print(
            f"No sink answered on 127.0.0.1:{smtp_port}.\n"
            f"Start one first:  mailpit   (UI: http://localhost:8025)\n"
            f"             or:  python3 -m tests.smtp_capture {smtp_port}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
