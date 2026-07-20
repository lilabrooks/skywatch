---
type: ADR
title: SQLite persistence layout and migrations
description: Single SQLite file at DB_PATH, WAL mode, PRAGMA user_version migrations in code; passes replaced-from-now on successful fetch, forecasts upserted per hour, cycles audited.
tags: [adr]
timestamp: 2026-07-10T23:49:31Z
status: accepted
---

# Status

Accepted (2026-07-19, by the owner)

# Context

The goal mandates SQLite with schema migrations and a later retention policy.
Open questions this ADR settles: where the file lives, how schema changes roll
forward, how re-fetched predictions are deduplicated (pass times jitter by
seconds between fetches as TLEs update, so a naive unique key on start time
would accumulate near-duplicate rows), and how concurrent readers (status page)
coexist with the writing cycle.

# Decision

- **One SQLite file** at `DB_PATH` (config; default `./skywatch.db`), created on
  first connect. The stdlib `sqlite3` driver per ADR-0001. WAL journal mode so
  page reads never block on a writing cycle; `foreign_keys` on.
- **Migrations**: an ordered list of SQL scripts in `skywatch/db.py`, tracked by
  `PRAGMA user_version`, applied transactionally at connect time. Forward-only;
  no down-migrations for a local single-operator DB.
- **Schema v1**: `passes` (normalized prediction rows: start/culmination/end
  UTC, max elevation, azimuth degrees + compass at rise/set, `visible` flag,
  source, fetched-at), `forecast_hours` (source, hour UTC, cloud-cover percent,
  fetched-at; unique per source+hour), `cycles` (started/finished timestamps
  plus per-source status strings, `ok` or `error: …`). Later milestones add
  tables (verdicts, digests) via new migrations.
- **Prediction dedup — replace-from-now**: on a *successful* passes fetch, one
  transaction deletes stored passes with `start_utc >= now` for that source and
  inserts the fresh set. Past rows are never touched (history), and a failed
  fetch deletes nothing, so stale-but-real predictions survive outages.
- **Forecast dedup — upsert**: hour rows conflict on `(source, hour_utc)` and
  the newest fetch wins; forecast history is the latest value per hour, not
  every revision.
- Destructive pruning (retention) is milestone 5 work and stays inside the data
  guardrails; this schema anticipates it with plain timestamp columns.

# Alternatives considered

- **Append-only snapshots** (keep every fetch's full prediction set, query the
  latest): a true audit log, but v1 has no consumer for prediction revisions,
  and every read becomes "latest snapshot" bookkeeping. More rows, more code,
  no user-visible benefit yet.
- **Fuzzy dedup on a rounded pass key** (e.g. culmination rounded to 10
  minutes): keeps one row per physical pass across fetches, but the rounding
  boundary still splits or merges passes occasionally — silent wrongness beats
  loud simplicity here, so replace-from-now won.
- **Default rollback journal instead of WAL**: simpler on paper, but the status
  page reads while the cycle writes; WAL removes reader/writer blocking with a
  local-file-only cost (`-wal`/`-shm` sidecar files, ignored by git).
- **A migration framework or ORM** (alembic, SQLAlchemy): dependencies for a
  problem two pragmas and a list solve; contradicts ADR-0001.

# Consequences

- `connect()` is the single choke point: every caller gets migrations applied
  and pragmas set for free; tests run against a temp path or `:memory:`.
- Replace-from-now means pass `id`s are not stable across fetches; nothing may
  hold a foreign key to a future pass row across cycles. Milestone 3 verdicts
  must join by pass identity (source + times), not by row id, or recompute per
  cycle.
- `DB_PATH`, `*.db`, `*.db-wal`, `*.db-shm` join `.env.example`/`.gitignore`;
  the config spec table gains `DB_PATH`.
- Forward-only migrations keep the mechanism ~30 lines; undoing a bad schema
  change on a local DB means restoring the file or deleting it and refetching.

# Rollback / revisit trigger

Revisit via a new ADR if: a consumer for prediction-revision history appears
(switch passes to append-only snapshots); multi-process access shows WAL
contention or corruption symptoms; or the migration list outgrows in-code SQL
(move to files). Rolling back the storage engine itself would follow an
ADR-0001 revision; the store module (`skywatch/db.py`) is the only layer that
speaks SQL, so the blast radius stays there.
