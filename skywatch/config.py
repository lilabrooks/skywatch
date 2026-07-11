"""Environment-based configuration.

Contract: docs/specs/config.md. All values come from the process environment;
`make run` sources `.env` before starting the process, so this module never
touches the filesystem. Validation collects every problem and fails startup
with one message listing them all.
"""

from __future__ import annotations

import os.path
import re
from dataclasses import dataclass, field
from datetime import time
from typing import Mapping, MutableMapping

HOST = "127.0.0.1"  # loopback only; widening this reopens ADR-0001
DEFAULT_PORT = 8000
DEFAULT_DB_PATH = "skywatch.db"
DEFAULT_CLOUD_GO_MAX = 30
DEFAULT_CLOUD_MAYBE_MAX = 70
DEFAULT_MIN_ELEVATION_DEG = 25.0
DEFAULT_SMTP_PORT = 1025  # Mailpit/local capture; real submission is usually 587
DEFAULT_SMTP_FROM = "skywatch@localhost"
DEFAULT_PASSES_BASE_URL = "https://sat.terrestre.ar/passes/25544"  # ADR-0002
DEFAULT_FORECAST_BASE_URL = "https://api.open-meteo.com/v1/forecast"  # ADR-0002
DEFAULT_FETCH_INTERVAL_MINUTES = 360
DEFAULT_RETENTION_DAYS = 30

_QUIET_HOURS_RE = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(Exception):
    """Raised by load_config with every validation problem collected."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(f"  {e}" for e in errors))


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    sender: str
    recipient: str
    user: str | None = None
    password: str | None = field(default=None, repr=False)
    starttls: bool = False


@dataclass(frozen=True)
class Config:
    latitude: float
    longitude: float
    port: int
    db_path: str = DEFAULT_DB_PATH
    cloud_go_max: int = DEFAULT_CLOUD_GO_MAX
    cloud_maybe_max: int = DEFAULT_CLOUD_MAYBE_MAX
    min_elevation_deg: float = DEFAULT_MIN_ELEVATION_DEG
    smtp: SmtpConfig | None = None
    passes_base_url: str = DEFAULT_PASSES_BASE_URL
    forecast_base_url: str = DEFAULT_FORECAST_BASE_URL
    fetch_interval_minutes: int = DEFAULT_FETCH_INTERVAL_MINUTES
    retention_days: int = DEFAULT_RETENTION_DAYS
    quiet_hours: tuple[time, time] | None = None  # local (start, end); None = never quiet
    host: str = HOST


def apply_env_file(environ: MutableMapping[str, str], path: str) -> list[str]:
    """Fill environ from a KEY=VALUE file for keys not already set to a value.

    A non-empty process-environment value always wins over the file, so
    `PORT=9000 make run` overrides `.env`. But a variable that is *set to an
    empty or whitespace-only string* counts as unset (matching the parsers
    below), so the file value fills it — otherwise `export LATITUDE=` in the
    shell would silently shadow a perfectly good `.env` and make `cp` look
    like a no-op. Comments, blank lines, an optional `export ` prefix, and
    single/double quotes around values are handled; a missing file is not an
    error. Returns the names applied, for logging (never values — the file
    holds secrets).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return []
    applied = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        existing = environ.get(name)
        if name and (existing is None or not existing.strip()):
            environ[name] = value
            applied.append(name)
    return applied


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
    unit: str = "decimal degrees",
    required: bool = True,
    default: float | None = None,
) -> float | None:
    spec = f"{unit} between {low:g} and {high:g} (e.g. {example})"
    raw = _get(env, name)
    if raw is None:
        if required:
            errors.append(f"{name}: required but not set — expected {spec}")
            return None
        return default
    try:
        value = float(raw)
    except ValueError:
        errors.append(f"{name}: expected {spec}, got {raw!r}")
        return None
    if not (low <= value <= high):  # also rejects nan/inf
        errors.append(f"{name}: {raw!r} is out of range — expected {spec}")
        return None
    return value


def _parse_int(
    env: Mapping[str, str],
    name: str,
    low: int,
    high: int,
    default: int,
    errors: list[str],
    unit: str = "an integer",
    example: str | None = None,
) -> int | None:
    spec = f"{unit} between {low} and {high}" + (f" (e.g. {example})" if example else "")
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError:
        errors.append(f"{name}: expected {spec}, got {raw!r}")
        return None
    if not (low <= value <= high):
        errors.append(f"{name}: {raw!r} is out of range — expected {spec}")
        return None
    return value


def _parse_bool(
    env: Mapping[str, str], name: str, default: bool, errors: list[str]
) -> bool | None:
    raw = _get(env, name)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    errors.append(f"{name}: expected yes/no (or true/false, 1/0, on/off), got {raw!r}")
    return None


def _parse_db_path(env: Mapping[str, str], name: str, errors: list[str]) -> str:
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


def _parse_base_url(
    env: Mapping[str, str], name: str, default: str, errors: list[str]
) -> str:
    """Testing-only escape hatch: point a source at a local fixture server."""
    raw = _get(env, name)
    if raw is None:
        return default
    if not raw.startswith(("http://", "https://")):
        errors.append(f"{name}: expected an http(s) URL, got {raw!r}")
        return default
    return raw


def _parse_quiet_hours(
    env: Mapping[str, str], name: str, errors: list[str]
) -> tuple[time, time] | None:
    spec = "a local window like 22:00-08:00 (may cross midnight); unset means no quiet hours"
    raw = _get(env, name)
    if raw is None:
        return None
    match = _QUIET_HOURS_RE.match(raw)
    if match is None:
        errors.append(f"{name}: expected {spec}, got {raw!r}")
        return None
    start_h, start_m, end_h, end_m = (int(g) for g in match.groups())
    if not (start_h <= 23 and end_h <= 23 and start_m <= 59 and end_m <= 59):
        errors.append(f"{name}: {raw!r} is not a valid time window — expected {spec}")
        return None
    start, end = time(start_h, start_m), time(end_h, end_m)
    if start == end:
        errors.append(
            f"{name}: start and end are equal ({raw!r}) — use unset for none; "
            f"an all-day quiet window would silence the digest entirely"
        )
        return None
    return (start, end)


def _parse_smtp(env: Mapping[str, str], errors: list[str]) -> SmtpConfig | None:
    host = _get(env, "SMTP_HOST")
    recipient = _get(env, "SMTP_TO")
    if host is None:
        if recipient is not None:
            errors.append(
                "SMTP_HOST: required when SMTP_TO is set — the digest needs a "
                "server to send through (e.g. 127.0.0.1 for a local Mailpit)"
            )
        return None
    if recipient is None:
        errors.append(
            "SMTP_TO: required when SMTP_HOST is set — the address the digest "
            "goes to (e.g. you@example.org)"
        )
    port = _parse_int(
        env, "SMTP_PORT", 1, 65535, DEFAULT_SMTP_PORT, errors,
        unit="a port number", example="1025",
    )
    sender = _get(env, "SMTP_FROM") or DEFAULT_SMTP_FROM
    user = _get(env, "SMTP_USER")
    password = _get(env, "SMTP_PASSWORD")
    if (user is None) != (password is None):
        errors.append(
            "SMTP_USER/SMTP_PASSWORD: set both or neither (got only "
            + ("SMTP_USER" if user is not None else "SMTP_PASSWORD")
            + ")"
        )
    starttls = _parse_bool(env, "SMTP_STARTTLS", False, errors)
    if recipient is None or port is None or starttls is None:
        return None
    return SmtpConfig(
        host=host,
        port=port,
        sender=sender,
        recipient=recipient,
        user=user,
        password=password,
        starttls=starttls,
    )


def load_config(env: Mapping[str, str]) -> Config:
    """Parse and validate configuration, raising ConfigError with all problems."""
    errors: list[str] = []
    latitude = _parse_float(env, "LATITUDE", -90, 90, "47.61", errors)
    longitude = _parse_float(env, "LONGITUDE", -180, 180, "-122.33", errors)
    port = _parse_int(env, "PORT", 1, 65535, DEFAULT_PORT, errors, example="8000")
    db_path = _parse_db_path(env, "DB_PATH", errors)
    cloud_go_max = _parse_int(
        env, "CLOUD_GO_MAX", 0, 100, DEFAULT_CLOUD_GO_MAX, errors,
        unit="a percentage", example="30",
    )
    cloud_maybe_max = _parse_int(
        env, "CLOUD_MAYBE_MAX", 0, 100, DEFAULT_CLOUD_MAYBE_MAX, errors,
        unit="a percentage", example="70",
    )
    min_elevation = _parse_float(
        env, "MIN_ELEVATION_DEG", 0, 90, "25", errors,
        unit="degrees above the horizon", required=False,
        default=DEFAULT_MIN_ELEVATION_DEG,
    )
    smtp = _parse_smtp(env, errors)
    fetch_interval = _parse_int(
        env, "FETCH_INTERVAL_MINUTES", 5, 1440, DEFAULT_FETCH_INTERVAL_MINUTES,
        errors, unit="minutes", example="360",
    )
    retention_days = _parse_int(
        env, "RETENTION_DAYS", 1, 3650, DEFAULT_RETENTION_DAYS,
        errors, unit="days", example="30",
    )
    quiet_hours = _parse_quiet_hours(env, "QUIET_HOURS", errors)
    passes_base_url = _parse_base_url(
        env, "PASSES_BASE_URL", DEFAULT_PASSES_BASE_URL, errors
    )
    forecast_base_url = _parse_base_url(
        env, "FORECAST_BASE_URL", DEFAULT_FORECAST_BASE_URL, errors
    )
    if (
        cloud_go_max is not None
        and cloud_maybe_max is not None
        and cloud_maybe_max < cloud_go_max
    ):
        errors.append(
            f"CLOUD_MAYBE_MAX: must be >= CLOUD_GO_MAX "
            f"(got {cloud_maybe_max} < {cloud_go_max})"
        )
    if errors:
        raise ConfigError(errors)
    assert (
        latitude is not None
        and longitude is not None
        and port is not None
        and cloud_go_max is not None
        and cloud_maybe_max is not None
        and min_elevation is not None
        and fetch_interval is not None
        and retention_days is not None
    )
    return Config(
        latitude=latitude,
        longitude=longitude,
        port=port,
        db_path=db_path,
        cloud_go_max=cloud_go_max,
        cloud_maybe_max=cloud_maybe_max,
        min_elevation_deg=min_elevation,
        smtp=smtp,
        passes_base_url=passes_base_url,
        forecast_base_url=forecast_base_url,
        fetch_interval_minutes=fetch_interval,
        retention_days=retention_days,
        quiet_hours=quiet_hours,
    )
