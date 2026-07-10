# Log

## 2026-07-10

- Milestone 1 (skeleton) done. Python 3.12+ stdlib-only stack proposed in **ADR-0001** (awaiting owner review): http.server, urllib, sqlite3, smtplib, threading, unittest, make. New: `skywatch/` package (config loading, loopback HTTP server with `/healthz`, entrypoint), `tests/` (18 tests), `Makefile` (`test`, `run`), `.env.example`, README stub, Python ignores in `.gitignore`. Spec added: `docs/specs/config.md` (env contract, fail-fast collected errors, exit 2); mapped in `okf-map.yml`. Recorded the lint decision in CLAUDE.md verification commands (compileall syntax pass inside `make test`; no third-party linter per ADR-0001). Verified: `make test` green offline; `make run` served `/healthz` → `{"status": "ok"}` (root 200, unknown path 404); `LATITUDE=banana make run` exited 2 naming the expected format. Note: Mailpit is not installed on this machine — needed no earlier than milestone 3's manual digest check; will flag before that lands.

## 2026-07-09

- Goal defined via the kit's goal interview (owner answers: stack delegated to proposed ADRs; v1 sources are the core ISS-passes × cloud-cover join only; digest channel is email over SMTP). Journal features — observation log, photo uploads/EXIF, user-data import/export — excluded by the owner as non-goals.
- Known future directions, acknowledged by the owner but deliberately outside the v1 goal (candidates for post-goal milestone proposals): meteor-shower and aurora sources; moon phase/darkness computed locally; paste-anything location and object-designation input (city names, map URLs, plus codes, comet designations); local ephemeris math with tolerance-based golden tests; an `.ics` calendar feed and, later, an OAuth calendar push; a Dockerfile and target-repo CI; a config-file schema; a `skywatch tonight` CLI companion.
