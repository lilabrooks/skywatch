---
type: Goal
title: Skywatch goal
description: A local always-on service that emails a digest when tonight's ISS pass is actually worth stepping outside for.
tags: [goal, milestones, service, iss, weather]
timestamp: 2026-07-09T00:00:00Z
owner: Lila Brooks
deciders: [Lila Brooks]
---

# Goal

Kind: service

Problem: Knowing whether tonight is worth stepping outside — a visible ISS pass under a clear sky — means juggling pass-prediction sites and an hourly cloud forecast, at the right time of day, every day.

Solution: Skywatch — a local always-on service that fetches ISS pass predictions and the cloud-cover forecast for a configured location on a schedule, joins them into per-pass visibility verdicts, stores history in SQLite, serves a small status page, and emails a digest only when tonight has a pass worth watching.

# Target state

- A scheduler runs a fetch → join → verdict cycle on a configurable interval, with a way to trigger one cycle on demand for testing.
- Two external sources, both public HTTP APIs: ISS pass predictions and hourly cloud cover for the configured latitude/longitude. Every fetch is mocked offline in tests; upstream timeouts and errors are mapped and survive the cycle.
- SQLite persistence for predictions, forecasts, and computed verdicts, with schema migrations and a retention policy that prunes old rows (destructive pruning stays inside the data guardrails).
- Verdict logic joins pass windows against cloud cover and pass quality (elevation/brightness) into go / maybe / skip per pass, with human-readable reasons (example digest line: "21:42–21:48, max elevation 74°, WSW→ENE, cloud 20% — GO").
- An email digest sent via SMTP configured from the environment: one email when tonight has a go/maybe pass, silence otherwise. The transport is testable at four layers: mocked notifier in unit tests, loopback capture server in `make test`, a local Mailpit inbox for the acceptance pass, and an owner-gated first real send.
- A status page served locally: upcoming passes, verdicts with reasons, last cycle time, and a clean empty state before any data exists.
- Configuration (location, thresholds, quiet hours, SMTP) comes from the environment and is documented with placeholder values in a committed `.env.example`.

# Success criteria

- `make test` passes fully offline: every HTTP interaction mocked, email asserted through a loopback capture server, no real network or credentials required.
- `make run` starts the scheduler and serves the status page locally; `curl` of the health endpoint returns ok.
- One triggered cycle against recorded fixtures writes predictions, forecasts, and verdicts to SQLite; the go-case fixture produces exactly one digest in the local mail sink, and the cloudy/no-pass fixture produces none.
- Input tolerance: missing or malformed configuration (garbage latitude, non-numeric threshold) fails fast at startup with a clear message naming the expected format — never a stack trace mid-cycle.
- No secrets in tracked files: `git check-ignore .env` passes and `.env.example` documents every variable with placeholders.

# Non-goals

- No observation journal, no photo uploads or EXIF parsing, and no import/export of user-authored data (owner's exclusion).
- No sources beyond ISS passes and cloud cover in v1 — meteor showers, aurora, and moon darkness are known future directions, not goals.
- No friendly location parsing in v1: configuration is numeric lat/lon only; anything else is rejected with a clear error. Paste-anything input (city names, map URLs, plus codes) is a known future direction.
- No accounts, no multi-user, no hosting or deployment automation; this runs locally for one operator.
- No LLM/AI features.

# Constraints

- Stack, web framework, HTTP client, scheduler mechanism, and test tooling are Claude Code's decisions via proposed ADRs in `docs/adr/` (owner delegated at the goal interview).
- External data comes only from public HTTP APIs for ISS passes and weather; every external interaction must be mockable offline.
- Secrets (SMTP credentials) come from the environment only and are never tracked; sending a real email or calling any side-effecting external service is owner-gated.
- Specs in `docs/specs/` govern the source, verdict, digest, and page contracts as they land.

# Milestones

Ordered backlog. When asked to continue without a specific task, Claude Code
takes the first unchecked milestone. Check a milestone off only when its
verification passes, and record progress in `docs/log.md`. A user-facing
milestone's verification names at least one rejected or edge input alongside
the happy path. When the backlog is empty, Claude Code runs a first-time-user
acceptance pass, reports the goal met, and proposes candidate milestones
(from `docs/log.md` known items, ADR revisit triggers, acceptance-pass
findings, and in-scope extensions); the owner chooses what gets added.

- [x] Skeleton: service scaffold with canonical commands (`make test`, `make run`), health endpoint, config loading, and test harness; stack recorded as a proposed ADR. Verify: `make test` passes; `make run` serves the health endpoint; startup with a garbage `LATITUDE` fails fast with a clear message naming the expected format.
- [x] Sources: fetch ISS passes and hourly cloud cover for the configured location into SQLite, normalized; offline tests via recorded fixtures, including timeout and upstream-error fixtures that the cycle survives. Verify: `make test`; a triggered cycle against mocks writes source rows.
- [x] Verdict and digest: join passes against cloud cover into go/maybe/skip with reasons; compose and send the digest through the SMTP transport; loopback capture tests assert exactly one send on the go fixture and zero sends on the cloudy fixture. Verify: `make test`; manual: a cycle against a local Mailpit inbox delivers one digest for the go fixture and none for the cloudy one.
- [x] Status page: upcoming passes, verdicts with reasons, and last-cycle time served locally, including a clean empty state with no data. Verify: `make test` covers routes and assets; manual browser check of both the populated and the empty-database states.
- [x] Scheduler and operations: interval scheduling with quiet hours, an on-demand cycle trigger, retention pruning behind an injectable clock, and a complete `.env.example`. Verify: `make test` scheduler and retention tests; `git check-ignore .env` passes.
- [x] README quickstart that reproduces on a clean checkout (setup, `make test`, `make run`, one Mailpit digest observed). Verify: follow the README from a fresh clone; setup, test, and run steps work as written.
