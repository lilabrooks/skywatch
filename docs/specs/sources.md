---
type: Spec
title: Source fetch, normalization, and storage contract
description: How the two upstreams are fetched, normalized into typed rows, stored in SQLite, and how per-source failures are survived by the cycle.
tags: [spec]
timestamp: 2026-07-10T23:56:10Z
---

# Purpose

Governs `skywatch/fetch.py`, `skywatch/sources.py`, `skywatch/cycle.py`,
`skywatch/db.py`, and `skywatch/model.py`: everything between the two upstream
APIs (chosen in ADR-0002) and the SQLite file (layout in ADR-0003). The verdict
join (milestone 3) and status page (milestone 4) consume the rows this contract
produces.

# Contract

**Fetch layer.** All upstream traffic goes through `http_get_json(url, timeout)`
(default timeout 10 s, `User-Agent: skywatch/<version>`). It returns parsed
JSON or raises `FetchError` for: non-2xx status, unreachable host, timeout, or
a non-JSON body. Callers inject a fake with the same signature in tests; no
test may hit the network.

**Sources and normalization.**

- Passes — `sat.terrestre.ar/passes/25544?lat&lon&limit=10`. Each upstream item
  (rise/culmination/set events) normalizes to one `Pass`: UTC `…Z` timestamps
  at second precision, `max_elevation_deg` from culmination altitude, azimuth
  degrees at rise/set plus 16-point compass names derived from them (e.g.
  247.5° → `WSW`), and the upstream pass-level `visible` flag (observer dark +
  ISS sunlit). Output is sorted by start time.
- Cloud cover — Open-Meteo `…/v1/forecast?hourly=cloud_cover&timezone=UTC&forecast_days=2`.
  Parallel `time[]`/`cloud_cover[]` arrays normalize to one `ForecastHour` per
  hour: UTC hour stamp, integer percent clamped to 0–100.
- Any shape surprise — non-list passes payload, missing keys, non-numeric
  values, mismatched array lengths — raises `SourceError` naming the offending
  item index. Example rejected input: a passes payload of
  `{"unexpected": "shape"}` is a recorded per-source error, never a crash.

**Storage semantics (ADR-0003).**

- Passes: on a *successful* fetch only, one transaction deletes this source's
  rows with `start_utc >=` the cycle start and inserts the fresh set — history
  stays, failed fetches delete nothing, re-runs do not duplicate.
- Forecast hours: upsert on `(source, hour_utc)`; the newest fetch wins.
- Every cycle writes an audit row: started/finished timestamps and a
  per-source status string (`ok: …` or `error: …`).

**Cycle isolation.** `run_cycle(conn, config, fetch_json, clock)` runs the two
sources independently: `FetchError`/`SourceError` from one source is recorded
in its status and logged, and the other source still runs to completion. Any
other exception is a bug and propagates. The clock is injectable; timestamps
in rows come from it.

# Verification

- `tests/test_fetch.py`: FetchError mapping against a real local HTTP server —
  200 JSON, HTTP 500, non-JSON body, timeout, connection refused.
- `tests/test_sources.py`: recorded fixtures (`tests/fixtures/*.json`, captured
  live 2026-07-10) normalize to the exact expected rows; malformed shapes raise
  `SourceError`.
- `tests/test_db.py`: migrations reach `user_version = len(MIGRATIONS)` in WAL
  mode; replace-from-now keeps history and swaps the future; forecast upsert
  keeps one row per hour.
- `tests/test_cycle.py`: the milestone verification — a triggered cycle against
  mocks writes 8 pass rows and 48 forecast rows; timeout, HTTP 500, and
  malformed-shape cases are survived per source, stored predictions outlive an
  outage, and repeat cycles do not duplicate.
- All offline inside `make test`.
