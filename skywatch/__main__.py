"""Entrypoint: `python3 -m skywatch` serves; `python3 -m skywatch cycle` runs
one fetch/verdict/digest cycle and exits (`make run` / `make cycle` source .env
first)."""

from __future__ import annotations

import logging
import os
import sys

from skywatch import db
from skywatch.config import Config, ConfigError, load_config
from skywatch.cycle import run_cycle
from skywatch.notify import build_notifier
from skywatch.server import make_server

log = logging.getLogger("skywatch")

USAGE = "usage: python3 -m skywatch [cycle]"


def _serve(config: Config) -> int:
    connection = db.connect(config.db_path)
    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    connection.close()
    log.info("database ready at %s (schema v%d)", config.db_path, schema_version)
    if config.smtp is None:
        log.info("digest disabled: SMTP not configured (set SMTP_HOST and SMTP_TO)")

    server = make_server(config.host, config.port)
    host, port = server.server_address[:2]
    log.info("serving on http://%s:%s (health: /healthz)", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()
    return 0


def _cycle_once(config: Config) -> int:
    notifier = build_notifier(config)
    if notifier is None:
        log.info("digest disabled: SMTP not configured (set SMTP_HOST and SMTP_TO)")
    connection = db.connect(config.db_path)
    try:
        result = run_cycle(connection, config, notifier=notifier)
    finally:
        connection.close()
    print(
        f"cycle {result.cycle_id}: passes {result.passes_status} | "
        f"forecast {result.forecast_status} | {result.verdict_count} verdicts | "
        f"digest {result.digest_status}"
    )
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if args not in ([], ["cycle"]):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        config = load_config(os.environ)
    except ConfigError as err:
        print(f"skywatch: configuration error\n{err}", file=sys.stderr)
        return 2
    if args == ["cycle"]:
        return _cycle_once(config)
    return _serve(config)


if __name__ == "__main__":
    sys.exit(main())
