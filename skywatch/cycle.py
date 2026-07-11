"""One fetch -> join -> verdict -> digest cycle (contracts:
docs/specs/sources.md and docs/specs/verdict-digest.md).

Each source fails independently: a timeout or shape error is recorded on the
cycle row and logged, and the rest of the cycle still runs — verdicts are
computed from whatever the store holds, so stale-but-real predictions keep
working through an outage. Only FetchError, SourceError, and NotifyError are
survivable; genuine bugs propagate.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, tzinfo as TzInfo
from typing import Callable

from skywatch import db, digest, sources
from skywatch.config import Config
from skywatch.fetch import FetchError, http_get_json
from skywatch.model import to_utc_z, utcnow
from skywatch.notify import Notifier, NotifyError
from skywatch.sources import SourceError
from skywatch.verdict import judge

log = logging.getLogger("skywatch.cycle")

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CycleResult:
    cycle_id: int
    passes_status: str
    forecast_status: str
    verdict_count: int
    digest_status: str

    @property
    def ok(self) -> bool:
        return self.passes_status.startswith("ok") and self.forecast_status.startswith("ok")


def _maybe_send_digest(
    conn: sqlite3.Connection,
    config: Config,
    verdicts,
    notifier: Notifier | None,
    now: datetime,
    tz: TzInfo | None,
) -> str:
    picked = digest.watchable(verdicts, now)
    if not picked:
        return "skipped: no watchable pass in the next 24h"
    local_date = now.astimezone(tz).date().isoformat()
    if db.digest_already_sent(conn, local_date):
        return f"skipped: already sent for {local_date}"
    if notifier is None:
        return "skipped: SMTP not configured"
    subject, body = digest.compose(picked, config.latitude, config.longitude, tz)
    try:
        notifier.send(subject, body)
    except NotifyError as err:
        log.warning("digest send failed: %s", err)
        return f"error: {err}"
    db.record_digest(conn, local_date, to_utc_z(now), subject, len(picked))
    log.info("digest sent for %s: %s", local_date, subject)
    return f"sent: {subject}"


def run_cycle(
    conn: sqlite3.Connection,
    config: Config,
    fetch_json: sources.FetchJson = http_get_json,
    clock: Clock = utcnow,
    notifier: Notifier | None = None,
    tz: TzInfo | None = None,
) -> CycleResult:
    started_at = to_utc_z(clock())
    cycle_id = db.start_cycle(conn, started_at)

    try:
        passes = sources.fetch_passes(fetch_json, config)
        db.replace_future_passes(
            conn, sources.PASSES_SOURCE, started_at, passes, to_utc_z(clock())
        )
        passes_status = f"ok: {len(passes)} passes"
    except (FetchError, SourceError) as err:
        passes_status = f"error: {err}"
        log.warning("passes fetch failed: %s", err)

    try:
        hours = sources.fetch_forecast(fetch_json, config)
        db.upsert_forecast_hours(conn, hours, to_utc_z(clock()))
        forecast_status = f"ok: {len(hours)} hours"
    except (FetchError, SourceError) as err:
        forecast_status = f"error: {err}"
        log.warning("forecast fetch failed: %s", err)

    # Judge from the store, not the fetch result: verdicts keep flowing from
    # stored predictions even when this cycle's fetches failed.
    verdicts = judge(db.future_passes(conn, started_at), db.forecast_map(conn), config)
    db.insert_verdicts(conn, cycle_id, verdicts, to_utc_z(clock()))
    digest_status = _maybe_send_digest(conn, config, verdicts, notifier, clock(), tz)

    db.finish_cycle(
        conn, cycle_id, to_utc_z(clock()), passes_status, forecast_status, digest_status
    )
    log.info(
        "cycle %d: passes %s | forecast %s | %d verdicts | digest %s",
        cycle_id, passes_status, forecast_status, len(verdicts), digest_status,
    )
    return CycleResult(cycle_id, passes_status, forecast_status, len(verdicts), digest_status)
