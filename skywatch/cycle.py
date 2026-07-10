"""One fetch -> normalize -> store cycle (contract: docs/specs/sources.md).

Each source fails independently: a timeout or shape error is recorded on the
cycle row and logged, and the other source still runs. Only FetchError and
SourceError are survivable; genuine bugs propagate.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from skywatch import db, sources
from skywatch.config import Config
from skywatch.fetch import FetchError, http_get_json
from skywatch.model import to_utc_z, utcnow
from skywatch.sources import SourceError

log = logging.getLogger("skywatch.cycle")

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CycleResult:
    cycle_id: int
    passes_status: str
    forecast_status: str

    @property
    def ok(self) -> bool:
        return self.passes_status.startswith("ok") and self.forecast_status.startswith("ok")


def run_cycle(
    conn: sqlite3.Connection,
    config: Config,
    fetch_json: sources.FetchJson = http_get_json,
    clock: Clock = utcnow,
) -> CycleResult:
    started_at = to_utc_z(clock())
    cycle_id = db.start_cycle(conn, started_at)

    try:
        passes = sources.fetch_passes(fetch_json, config.latitude, config.longitude)
        db.replace_future_passes(
            conn, sources.PASSES_SOURCE, started_at, passes, to_utc_z(clock())
        )
        passes_status = f"ok: {len(passes)} passes"
    except (FetchError, SourceError) as err:
        passes_status = f"error: {err}"
        log.warning("passes fetch failed: %s", err)

    try:
        hours = sources.fetch_forecast(fetch_json, config.latitude, config.longitude)
        db.upsert_forecast_hours(conn, hours, to_utc_z(clock()))
        forecast_status = f"ok: {len(hours)} hours"
    except (FetchError, SourceError) as err:
        forecast_status = f"error: {err}"
        log.warning("forecast fetch failed: %s", err)

    db.finish_cycle(conn, cycle_id, to_utc_z(clock()), passes_status, forecast_status)
    log.info("cycle %d: passes %s | forecast %s", cycle_id, passes_status, forecast_status)
    return CycleResult(cycle_id, passes_status, forecast_status)
