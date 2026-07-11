---
type: Spec
title: Verdict and digest contract
description: The go/maybe/skip rules joining passes to cloud cover, and when exactly one digest email goes out.
tags: [spec]
timestamp: 2026-07-11T00:11:34Z
---

# Purpose

Governs `skywatch/verdict.py`, `skywatch/digest.py`, and `skywatch/notify.py`,
plus the digest steps of `skywatch/cycle.py`: how stored passes and forecast
hours become go/maybe/skip verdicts with human-readable reasons, and the
conditions under which the SMTP digest is sent. The status page (milestone 4)
renders these verdicts; the scheduler (milestone 5) adds quiet hours on top.

# Contract

**Verdict rules** — evaluated per pass, first match wins, judged from the
*store* each cycle (so verdicts keep flowing from stored predictions during an
upstream outage):

1. Upstream `visible` false → **skip**, "not visible (daylight, or the ISS
   sits in Earth's shadow)". Weather cannot rescue an invisible pass.
2. `max_elevation_deg < MIN_ELEVATION_DEG` (default 25) → **skip**, "too low",
   naming the configured minimum.
3. Cloud cover for the pass = the **worst (max)** `cloud_cover_pct` over the
   forecast hours the pass window touches. No hour covered → **maybe**,
   "no cloud forecast for this window yet".
4. cloud ≤ `CLOUD_GO_MAX` (default 30) → **go**; cloud ≤ `CLOUD_MAYBE_MAX`
   (default 70) → **maybe**; else → **skip** ("overcast").

Reasons always carry the numbers they were decided on (cloud %, elevation °).
Every future pass gets a verdict row per cycle (`verdicts` table, denormalized
pass fields, keyed to the cycle) — including skips, so the page can show *why*
tonight is a no.

**Digest selection.** A pass is digest-worthy when its verdict is go or maybe
and it starts within the next 24 h. If none qualifies, no email — silence is
the feature. Dedup: at most one digest per local calendar date (`digests`
table, unique on local date), recorded only after a successful send, so a
transport failure is retried by the next cycle and a repeated cycle never
resends. Precedence of recorded outcomes: no watchable pass → already sent →
SMTP unconfigured → send (or transport error).

**Digest format.** Plain text, times in the machine's local timezone. Subject:
count, first start time, its verdict, best elevation. One line per pass in the
goal's format — `21:42–21:48, max elevation 74°, WSW→ENE, cloud 20% — GO` —
followed by the reason, then a location footer. Unknown cloud renders as
"cloud unknown", never a fabricated number.

**Transport.** `Notifier.send(subject, body)` is the seam (ADR-0004).
`NotifyError` is survivable and recorded as the cycle's digest status;
anything else propagates as a bug.

# Verification

- `tests/test_verdict.py`: every rule above, including the worst-hour rule for
  passes straddling an hour boundary and config-driven thresholds.
- `tests/test_digest.py`: window filtering (past, >24 h, skips), ordering,
  goal-format line, unknown-cloud rendering, empty-compose rejection.
- `tests/test_notify.py`: real `SMTPNotifier` against the loopback capture
  server (headers, body, dot-stuffing round-trip); unreachable server →
  `NotifyError`.
- `tests/test_cycle.py`: go fixture → exactly one send (both via the fake and
  via real SMTP over a loopback socket); recorded overcast fixture → zero
  sends; same-day rerun → no resend; failed send → retried next cycle;
  unconfigured SMTP → recorded skip.
- Manual (2026-07-10): `make cycle` against a local fixture HTTP server and
  the standalone capture sink delivered exactly one digest on the clear-sky
  forecast and none on the recorded overcast one. Mailpit-inbox variant
  pending (Mailpit not installed on this machine).
