"""Entrypoint: `python3 -m skywatch` (or `make run`, which sources .env first)."""

from __future__ import annotations

import logging
import os
import sys

from skywatch.config import ConfigError, load_config
from skywatch.server import make_server

log = logging.getLogger("skywatch")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        config = load_config(os.environ)
    except ConfigError as err:
        print(f"skywatch: configuration error\n{err}", file=sys.stderr)
        return 2

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


if __name__ == "__main__":
    sys.exit(main())
