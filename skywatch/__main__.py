"""Entrypoint: `python3 -m skywatch` serves; `python3 -m skywatch cycle` runs
one fetch/verdict/digest cycle and exits (`make run` / `make cycle` source .env
first)."""

from __future__ import annotations

import logging
import os
import sys

from skywatch import db
from skywatch.config import Config, ConfigError, apply_env_file, load_config
from skywatch.cycle import CycleRunner, run_cycle
from skywatch.notify import build_notifier
from skywatch.scheduler import Scheduler
from skywatch.server import make_server

log = logging.getLogger("skywatch")

USAGE = "usage: python3 -m skywatch [cycle]"


def _serve(config: Config) -> int:
    connection = db.connect(config.db_path)
    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    connection.close()
    log.info("database ready at %s (schema v%d)", config.db_path, schema_version)
    notifier = build_notifier(config)
    if notifier is None:
        log.info("digest disabled: SMTP not configured (set SMTP_HOST and SMTP_TO)")
    if config.quiet_hours is not None:
        start, end = config.quiet_hours
        log.info("quiet hours: no digests between %s and %s local", f"{start:%H:%M}", f"{end:%H:%M}")

    runner = CycleRunner(config, notifier=notifier)
    try:
        server = make_server(config, trigger=runner.run)
    except OSError as err:
        print(
            f"skywatch: cannot bind http://{config.host}:{config.port} — "
            f"{err.strerror or err}. Is something already using this port? "
            f"Set PORT to a free one (e.g. PORT=8100 make run).",
            file=sys.stderr,
        )
        return 2
    scheduler = Scheduler(runner.run, interval_seconds=config.fetch_interval_minutes * 60)
    host, port = server.server_address[:2]
    scheduler.start()
    log.info(
        "serving on http://%s:%s (health: /healthz, trigger: POST /cycle); "
        "cycle now, then every %d min",
        host, port, config.fetch_interval_minutes,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        scheduler.stop()
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
    env_file = os.environ.get("SKYWATCH_ENV_FILE", ".env")
    env_file_present = bool(env_file) and os.path.isfile(env_file)
    if env_file:
        applied = apply_env_file(os.environ, env_file)
        if applied:
            log.info(
                "loaded %d value(s) from %s (a non-empty environment value wins)",
                len(applied), env_file,
            )
    try:
        config = load_config(os.environ)
    except ConfigError as err:
        hint = ""
        if env_file and not env_file_present:
            hint = (
                f"\nhint: no {env_file} file found in {os.getcwd()} — "
                f"create one first:  cp .env.example {env_file}"
            )
        print(f"skywatch: configuration error\n{err}{hint}", file=sys.stderr)
        return 2
    if args == ["cycle"]:
        return _cycle_once(config)
    return _serve(config)


if __name__ == "__main__":
    sys.exit(main())
