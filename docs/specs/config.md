---
type: Spec
title: Configuration contract
description: Environment variables, their formats and defaults, and the fail-fast startup behavior on bad configuration.
tags: [spec]
timestamp: 2026-07-10T23:44:20Z
---

# Purpose

Governs how Skywatch is configured (`skywatch/config.py`) and what happens at
startup when configuration is missing or malformed. Every later surface
(sources, verdicts, digest, scheduler) reads its knobs through this contract.
The goal's success criteria depend on it directly: bad config must fail fast
with a clear message naming the expected format, never a stack trace mid-cycle.

# Contract

Configuration comes from the process environment, backed by an env file: at
startup the app fills in values from `.env` (path overridable via
`SKYWATCH_ENV_FILE`; set it to an empty string to disable loading, which the
test suite does for hermeticity) **for variables not already set to a
non-empty value** — a real process-environment value always wins, so
`PORT=9000 make run` overrides `.env` rather than being silently ignored. A
variable set to an empty or whitespace-only string counts as unset everywhere,
including here: the file value fills it, so `export LATITUDE=` in the shell
does not shadow a good `.env`. The file format is `KEY=VALUE` lines; comments,
blanks, an optional `export ` prefix, and quoted values are accepted; a
missing file is fine. Only the count of applied variables is logged, never
values. When required configuration is missing and no env file was found,
startup adds a hint to `cp .env.example .env`.

Variables as of milestone 1 (later milestones extend this table):

| Variable            | Required | Format                                                   | Default              |
|---------------------|----------|----------------------------------------------------------|----------------------|
| `LATITUDE`          | yes      | decimal degrees, −90 to 90 (north positive)              | —                    |
| `LONGITUDE`         | yes      | decimal degrees, −180 to 180 (east positive)             | —                    |
| `PORT`              | no       | integer, 1 to 65535                                      | `8000`               |
| `DB_PATH`           | no       | path for the SQLite file; parent dir must exist          | `skywatch.db`        |
| `CLOUD_GO_MAX`      | no       | percentage, 0 to 100                                     | `30`                 |
| `CLOUD_MAYBE_MAX`   | no       | percentage, 0 to 100; must be ≥ `CLOUD_GO_MAX`           | `70`                 |
| `MIN_ELEVATION_DEG` | no       | degrees above the horizon, 0 to 90                       | `25`                 |
| `SMTP_HOST`         | no*      | hostname/IP; unset ⇒ digest disabled                     | —                    |
| `SMTP_PORT`         | no       | port, 1 to 65535                                         | `1025` (local sink)  |
| `SMTP_TO`           | no*      | recipient address; required iff `SMTP_HOST` set          | —                    |
| `SMTP_FROM`         | no       | sender address                                           | `skywatch@localhost` |
| `SMTP_USER`         | no       | with `SMTP_PASSWORD` (both or neither)                   | —                    |
| `SMTP_PASSWORD`     | no       | secret; env/`.env` only, excluded from config repr      | —                    |
| `SMTP_STARTTLS`     | no       | yes/no (true/false, 1/0, on/off)                         | `no`                 |
| `FETCH_INTERVAL_MINUTES` | no  | minutes between cycles, 5 to 1440                        | `360`                |
| `RETENTION_DAYS`    | no       | days of history kept, 1 to 3650                          | `30`                 |
| `QUIET_HOURS`       | no       | local window `HH:MM-HH:MM`, may cross midnight; unset ⇒ none | —                |
| `PASSES_BASE_URL`   | no       | http(s) URL — testing-only override of ADR-0002 upstream | real upstream        |
| `FORECAST_BASE_URL` | no       | http(s) URL — testing-only override of ADR-0002 upstream | real upstream        |
| `SKYWATCH_ENV_FILE` | no       | env-file path; empty string disables loading             | `.env`               |

`*` `SMTP_HOST` and `SMTP_TO` are optional as a pair: setting either one
requires the other; setting neither disables the digest (recorded per cycle as
`skipped: SMTP not configured`).

- The server binds `127.0.0.1` only; the host is not configurable (ADR-0001).
- Range checks reject `nan` and `inf`. Unknown environment variables are ignored.
- Validation collects **all** problems, not just the first. On any problem the
  process prints `skywatch: configuration error` followed by one indented line
  per problem to stderr and exits with code **2**, before binding any socket.
- Each problem line names the variable, the expected format with an example,
  and the offending value when there was one. Example rejected input —
  `LATITUDE=banana` produces:
  `LATITUDE: expected decimal degrees between -90 and 90 (e.g. 47.61), got 'banana'`
- The same fail-fast rule covers binding: a `PORT` already in use exits 2
  with a message naming the port and suggesting a free one — never a
  traceback — and before the boot cycle fires.
- `.env.example` documents every variable with placeholder values only and must
  stay in step with this table.

# Verification

- Automated: `tests/test_config.py` (parsing, defaults, ranges, empty-as-unset,
  error collection, env-file loading rules) and `tests/test_startup.py`
  (subprocess exits 2 on garbage `LATITUDE` with the message above and no
  traceback; boots and serves `/healthz` on valid config; environment-beats-
  file precedence at process level; taken `PORT` exits 2 with a clear
  message). Both run offline in `make test`.
- Manual: `LATITUDE=banana LONGITUDE=-122.33 make run` exits 2 with the
  message above.
