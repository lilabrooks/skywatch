---
type: Spec
title: Status page contract
description: What the local page serves — upcoming verdicts with reasons, last-cycle line, empty states — and its safety rules (escaping, loopback, 500-not-traceback).
tags: [spec]
timestamp: 2026-07-11T00:20:23Z
---

# Purpose

Governs `skywatch/server.py` and `skywatch/page.py`: the local HTTP surface an
operator looks at. It reads the store written by the cycle (sources spec) and
renders the verdicts (verdict-digest spec); it never fetches upstream or
mutates anything.

# Contract

**Routes** (GET only, bound to 127.0.0.1 per ADR-0001):

- `/` — the status page (HTML).
- `/style.css` — the stylesheet, served from a module constant (no file I/O).
- `/healthz` — `{"status": "ok"}`, `application/json`; the liveness check.
- anything else — 404 text.

**Page content.**

- Header with the configured location (2-decimal lat/lon).
- A last-cycle line: local start time plus the three cycle statuses (passes,
  forecast, digest) exactly as recorded — including error text, so an operator
  sees upstream failures without reading logs.
- Upcoming passes: the newest cycle's verdicts whose window hasn't ended
  (`end_utc >= now`), soonest first — local time window, max elevation,
  compass path, cloud % (or `—` when unknown), a go/maybe/skip badge, and the
  human-readable reason. Skips are shown *with* reasons: "why not tonight" is
  half the page's job.
- Empty states, both deliberate: no cycles at all → "No data yet" with the
  `make cycle` hint; cycles but no upcoming passes → "No upcoming passes".
- Times render in the machine's local timezone (same rule as the digest).

**Safety.**

- Every dynamic value is HTML-escaped (cycle statuses can embed upstream error
  text); badge CSS classes come from a whitelist, never from data.
- A page-render failure (e.g. unopenable DB) returns a plain 500 with no
  traceback in the body; the traceback goes to the server log.
- Each request opens and closes its own SQLite connection; WAL (ADR-0003)
  keeps reads unblocked while a cycle writes.

# Verification

- `tests/test_server.py`: all four routes, the empty state over HTTP, the
  populated page after a real cycle against fixtures, and the broken-DB 500
  (no traceback in body).
- `tests/test_page.py`: empty state, populated rows (times, badge, reason,
  compass), the no-upcoming-passes state, HTML escaping of hostile status
  text, stylesheet badge classes.
- Manual (2026-07-10): browser check of both states — fresh empty DB (clean
  empty state, dark scheme respected) and a fixture-seeded DB (last-cycle line
  with sent-digest subject; GO/SKIP badges with reasons).
