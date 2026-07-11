---
type: ADR
title: SMTP digest transport, gating, and test layers
description: smtplib transport behind a Notifier seam; credentials env-only and never in repr; default port 1025 targets a local sink; real sends owner-gated by configuration; four test layers.
tags: [adr]
timestamp: 2026-07-11T00:11:34Z
status: proposed
---

# Status

Proposed (authored per the decision policy; awaiting owner review)

# Context

The digest leaves the machine over SMTP — the one side-effecting external
integration in the goal, and security-sensitive (credentials, outbound mail).
The goal demands the transport be testable at four layers and that real sends
stay owner-gated. Python 3.12 removed stdlib `smtpd`, so the loopback test
server question also needed settling.

# Decision

- **Transport**: stdlib `smtplib` with a 10 s timeout, wrapped in `SMTPNotifier`
  behind a minimal `Notifier` protocol (`send(subject, body)`), so everything
  above the transport depends only on that seam. Failures map to `NotifyError`,
  which a cycle records and survives (a failed send is retried by the next
  cycle because the digest-dedup row is written only after a successful send —
  at-least-once per day, never spam).
- **Credentials and gating**: SMTP settings come from the environment only
  (`SMTP_HOST`, `SMTP_PORT`, `SMTP_TO`, `SMTP_FROM`, `SMTP_USER`,
  `SMTP_PASSWORD`, `SMTP_STARTTLS`). The password field is excluded from
  dataclass repr so it cannot leak into logs. With no `SMTP_HOST`/`SMTP_TO`
  the digest is disabled and the cycle records `skipped: SMTP not configured`.
  `SMTP_PORT` defaults to **1025** — the local Mailpit/capture convention — so
  the out-of-the-box configuration cannot reach a real mail server; sending
  real mail requires the owner to deliberately point `SMTP_HOST`/`SMTP_PORT`
  at one and (usually) set `SMTP_STARTTLS=yes` plus credentials. That is the
  owner gate.
- **Test layers** (per the goal): (1) `RecordingNotifier` fake at the seam in
  unit tests; (2) a hand-rolled loopback SMTP capture server
  (`tests/smtp_capture.py`, ~90 lines of ESMTP: EHLO/MAIL/RCPT/DATA with
  dot-unstuffing) exercised by the real `SMTPNotifier` inside `make test`;
  (3) the same capture module runs standalone (`python3 -m tests.smtp_capture`)
  as a local inbox for manual checks, with Mailpit as the acceptance-pass
  inbox — `scripts/demo_digest.py` (`make demo`) drives this layer
  deterministically by time-shifting the recorded fixtures so one digest
  always sends, whatever tonight's real sky does; (4) an owner-run first
  real send.
- **AUTH/TLS scope**: `starttls()` and `login()` are invoked only when
  configured; the capture server implements neither (it exists to capture, not
  to authenticate). TLS-path testing happens at layer 4 against a real server.

# Alternatives considered

- **aiosmtpd as a dev dependency** for the capture server: maintained and
  featureful, but it drags in an async framework for what ~90 lines of
  blocking socket code covers, and it would be the repo's first package —
  against ADR-0001 for a test-only need.
- **HTTP mail APIs** (Mailgun/SES/Sendgrid): hosted accounts, API keys, and
  vendor lock for a single local operator; SMTP is the goal's stated channel.
- **An explicit `SMTP_REAL_SEND=yes` flag** as the owner gate: considered, but
  a flag that must be flipped alongside already-explicit host/port/credential
  configuration is double bookkeeping; pointing the transport at a real server
  *is* the deliberate act. Revisit if a near-miss shows this is too thin.

# Consequences

- Everything above the transport tests fast and offline; `make test` still
  needs no network (loopback sockets only).
- The capture server is ours to maintain; it implements the minimum ESMTP the
  real client emits, so smtplib behavior changes could require touching it.
- Default-1025 gating means a fresh `.env` copied from the example sends to a
  local sink, never to the internet.
- Must stay in sync: `.env.example` and `docs/specs/config.md` document the
  SMTP variables; `docs/specs/verdict-digest.md` states send/dedup semantics.

# Rollback / revisit trigger

Revisit via a new ADR if: the capture server proves flaky under `make test`
(swap in aiosmtpd as a dev dependency); the owner wants HTML mail, multiple
recipients, or a non-SMTP channel; or the implicit owner gate proves too weak
in practice (add the explicit flag). Rolling back the transport touches only
`skywatch/notify.py` and the SMTP config block.
