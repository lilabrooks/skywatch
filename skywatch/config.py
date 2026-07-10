"""Environment-based configuration.

Contract: docs/specs/config.md. All values come from the process environment;
`make run` sources `.env` before starting the process, so this module never
touches the filesystem. Validation collects every problem and fails startup
with one message listing them all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

HOST = "127.0.0.1"  # loopback only; widening this reopens ADR-0001
DEFAULT_PORT = 8000
DEFAULT_DB_PATH = "skywatch.db"


class ConfigError(Exception):
    """Raised by load_config with every validation problem collected."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(f"  {e}" for e in errors))


@dataclass(frozen=True)
class Config:
    latitude: float
    longitude: float
    port: int
    db_path: str = DEFAULT_DB_PATH
    host: str = HOST


def _get(env: Mapping[str, str], name: str) -> str | None:
    """A set-but-empty variable counts as unset."""
    value = env.get(name, "").strip()
    return value or None


def _parse_float(
    env: Mapping[str, str],
    name: str,
    low: float,
    high: float,
    example: str,
    errors: list[str],
) -> float | None:
    spec = f"decimal degrees between {low:g} and {high:g} (e.g. {example})"
    raw = _get(env, name)
    if raw is None:
        errors.append(f"{name}: required but not set — expected {spec}")
        return None
    try:
        value = float(raw)
    except ValueError:
        errors.append(f"{name}: expected {spec}, got {raw!r}")
        return None
    if not (low <= value <= high):  # also rejects nan/inf
        errors.append(f"{name}: {raw!r} is out of range — expected {spec}")
        return None
    return value


def _parse_port(env: Mapping[str, str], name: str, errors: list[str]) -> int | None:
    spec = f"an integer between 1 and 65535 (e.g. {DEFAULT_PORT})"
    raw = _get(env, name)
    if raw is None:
        return DEFAULT_PORT
    try:
        value = int(raw, 10)
    except ValueError:
        errors.append(f"{name}: expected {spec}, got {raw!r}")
        return None
    if not (1 <= value <= 65535):
        errors.append(f"{name}: {raw!r} is out of range — expected {spec}")
        return None
    return value


def _parse_db_path(env: Mapping[str, str], name: str, errors: list[str]) -> str:
    import os.path

    raw = _get(env, name)
    if raw is None:
        return DEFAULT_DB_PATH
    parent = os.path.dirname(raw)
    if parent and not os.path.isdir(parent):
        errors.append(
            f"{name}: directory {parent!r} does not exist — "
            f"expected a writable path for the SQLite file (e.g. {DEFAULT_DB_PATH})"
        )
    return raw


def load_config(env: Mapping[str, str]) -> Config:
    """Parse and validate configuration, raising ConfigError with all problems."""
    errors: list[str] = []
    latitude = _parse_float(env, "LATITUDE", -90, 90, "47.61", errors)
    longitude = _parse_float(env, "LONGITUDE", -180, 180, "-122.33", errors)
    port = _parse_port(env, "PORT", errors)
    db_path = _parse_db_path(env, "DB_PATH", errors)
    if errors:
        raise ConfigError(errors)
    assert latitude is not None and longitude is not None and port is not None
    return Config(latitude=latitude, longitude=longitude, port=port, db_path=db_path)
