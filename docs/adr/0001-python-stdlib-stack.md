---
type: ADR
title: Python standard-library-only runtime stack
description: Python 3.12+ with zero third-party runtime dependencies; stdlib http.server, urllib, sqlite3, smtplib, threading, unittest; make as the command runner.
tags: [adr]
timestamp: 2026-07-10T23:37:15Z
status: proposed
---

# Status

Proposed (authored per the decision policy; awaiting owner review)

# Context

Skywatch is a local, single-operator, always-on service (see `docs/GOAL.md`). It needs: an HTTP client for two public JSON APIs, SQLite persistence, SMTP sending, a small local status page, and an interval scheduler. Everything must be testable fully offline, and the repo guardrails make every new runtime dependency a decision with a named maintenance and security tradeoff. The goal interview delegated stack, web framework, HTTP client, scheduler mechanism, and test tooling to Claude Code via proposed ADRs. The README-quickstart milestone rewards a setup that reproduces on a clean checkout with minimal steps.

# Decision

Python ≥ 3.12, standard library only at runtime — zero third-party packages, no virtualenv, no pip step:

- **HTTP server** (status page, health endpoint): `http.server.ThreadingHTTPServer` with a hand-written handler, bound to `127.0.0.1` only.
- **HTTP client** (ISS passes, cloud cover): `urllib.request` with explicit timeouts, wrapped in one small fetch module so tests inject fakes.
- **Persistence**: the stdlib `sqlite3` module (SQLite itself is mandated by the goal; this pins the driver).
- **SMTP**: `smtplib` for the transport; the test-side loopback capture server is hand-rolled on `socketserver` (the stdlib `smtpd` module was removed in 3.12).
- **Scheduler**: a `threading`-based interval loop with an injectable clock — no cron parsing, no job-queue dependency.
- **Tests**: stdlib `unittest` via `python3 -m unittest discover`; `make` (present on macOS by default) as the canonical command runner (`make test`, `make run`).
- **Version floor**: developed against Python 3.14 (present on the owner's machine); source stays compatible with 3.12+, and nothing below 3.12 is tested or supported.

# Alternatives considered

- **Go**: excellent fit for an always-on local daemon (single binary, strong stdlib HTTP), but SQLite requires a third-party driver (`mattn/go-sqlite3` CGo or `modernc.org/sqlite`), which contradicts the zero-dependency aim, and iteration on a spec-driven exploratory repo is slower.
- **Node/TypeScript**: would need a SQLite driver, a scheduler package, and build tooling before the first test runs; the heaviest dependency surface of the options.
- **Python with FastAPI + httpx + APScheduler + pytest**: the best ergonomics, but four dependency trees to track for features this service barely uses (async, dependency injection, cron expressions). Each would need its own security/maintenance justification under the guardrails.
- **pytest alone as a dev dependency**: nicer assertions and fixtures than `unittest`, but it breaks the "clean checkout → `make test`, no install step" property, which is worth more here than test ergonomics at this repo's size.

# Consequences

- `make test` and `make run` work on a clean checkout with only Python 3.12+ present; the quickstart has no install step.
- Some small components are hand-rolled instead of imported: the SMTP loopback capture server (~80 lines, lands with the digest milestone), the scheduler loop, and `.env` loading (~25 lines in `skywatch/config.py`: the app fills unset variables from the file at startup and the process environment always wins — originally the Makefile sourced `.env`, which inverted that precedence and was fixed after the acceptance pass caught it).
- `unittest` is wordier than pytest (no fixtures/parametrize); acceptable at this scale.
- `http.server` is documented as not production-hardened; acceptable because the service binds loopback only, for one local operator, with no untrusted exposure. This must stay in sync: any change that exposes the server beyond loopback reopens this ADR.
- Later spec work (sources, digest, page) builds on these primitives and should not introduce packages casually; any new runtime dependency needs its own ADR.

# Rollback / revisit trigger

Revisit via a new ADR if any of these is observed: the server needs non-loopback binding, TLS, or auth; the hand-rolled SMTP capture proves flaky in `make test`; fetch requirements outgrow `urllib` (retry/backoff policies, HTTP/2, connection pooling); or `unittest` friction measurably slows milestone work. Rolling back means swapping the affected primitive for a dependency chosen in that new ADR — module boundaries (fetch wrapper, notifier interface, server module) are kept narrow so a swap stays local.
