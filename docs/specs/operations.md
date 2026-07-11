---
type: Spec
title: Scheduler and operations contract
description: Interval scheduling, quiet hours, the on-demand cycle trigger, and retention pruning.
tags: [spec]
timestamp: 2026-07-11T15:28:18Z
---

# Purpose

Governs how cycles get run and how history stays bounded: `skywatch/scheduler.py`,
the `CycleRunner` and pruning steps of `skywatch/cycle.py`/`skywatch/db.py`,
the quiet-hours gate, and the server's `POST /cycle` trigger. This is the
"always-on" half of the goal.

# Contract

**Scheduling.** Serve mode (`make run`) starts a daemon thread that runs one
cycle immediately (a fresh install shows data right away), then one every
`FETCH_INTERVAL_MINUTES` (default 360). A crashing cycle is logged and the
schedule continues — one bad run must never end the service. `stop()` is
prompt even mid-wait. Scheduler and trigger share one `CycleRunner`, which
serializes runs with a lock (no concurrent double-fetch) and opens a fresh
SQLite connection per run.

**On-demand trigger.** Two equivalent entry points run one cycle now:
`make cycle` (own process, prints the result line, exit 0 when both sources
fetched ok, 1 otherwise) and `POST /cycle` on the running server (200 with a
JSON status summary; 503 when no runner is wired, i.e. outside serve mode;
crash → 500 with no traceback in the body). GET on `/cycle` is a 404 — the
trigger mutates, so it is POST-only.

**Quiet hours.** `QUIET_HOURS` (optional local window `HH:MM-HH:MM`, may cross
midnight, start inclusive / end exclusive) suppresses *digest sending only* —
fetching and verdicts continue, and the skip is recorded as
`skipped: quiet hours (22:00-08:00)` **without** marking the day sent, so the
digest goes out after the window ends if the pass is still ahead; a pass that
has already started by then no longer qualifies (the watchable window only
looks forward). Outcome precedence per cycle: no watchable pass → already
sent → quiet hours → SMTP unconfigured → send (or transport error).

**Retention.** Each cycle ends by pruning rows strictly older than
`RETENTION_DAYS` (default 30) behind the cycle's injectable clock: passes and
verdicts by their end time, forecast hours by their hour, cycles by their
start, digests by their local date. A verdict also goes when its owning cycle
is pruned, so the foreign key never trips. Rows exactly at the cutoff stay.
Pruning is the only destructive write in the system and is bounded by the
cutoff; per-table counts are logged when anything was deleted.

# Verification

- `tests/test_scheduler.py`: immediate run, interval cadence, prompt stop,
  crash survival, `run_immediately=False`.
- `tests/test_db.py` (RetentionTests): only-older-than-cutoff pruned across
  all five tables, the FK edge (old cycle owning a fresh verdict), the
  at-cutoff boundary, and the empty-DB no-op.
- `tests/test_cycle.py`: quiet-hours skip that does not consume the day's
  send (and the later same-day send), pruning running with the cycle,
  `CycleRunner` sharing state across runs.
- `tests/test_server.py` (CycleTriggerTests): POST /cycle happy path, 503
  unwired, 404 elsewhere, 500 without traceback.
- `tests/test_config.py` (OperationsConfigTests): defaults, overrides, and
  rejected inputs for the three new variables.
- Manual (2026-07-11): serve mode against local fixture servers — boot cycle
  ran immediately, `curl -X POST /cycle` returned the JSON summary, page and
  health stayed live; `git check-ignore .env` passes.
