# Skywatch

A local always-on service that emails you a digest when tonight's ISS pass is
worth stepping outside for. It fetches pass predictions
([sat.terrestre.ar](https://sat.terrestre.ar)) and the hourly cloud-cover
forecast ([Open-Meteo](https://open-meteo.com)) for your location on a
schedule, joins them into **go / maybe / skip** verdicts with reasons, keeps
history in SQLite, serves a small status page, and stays silent unless
tonight qualifies.

A digest line looks like:

    21:42–21:48, max elevation 74°, WSW→ENE, cloud 5% — GO

## Requirements

Python 3.12+ and `make`. No packages to install, no virtualenv — the runtime
is standard library only.

## Quickstart

```sh
cp .env.example .env    # then edit: your LATITUDE/LONGITUDE (decimal degrees)
make test               # offline test suite — no network, no credentials
make run                # status page: http://127.0.0.1:8000
```

`make run` fetches immediately, then every `FETCH_INTERVAL_MINUTES`
(default 6 h). The page shows upcoming passes with verdicts and reasons —
including why tonight is a *no* — plus the last cycle's outcome. Health check:
`curl http://127.0.0.1:8000/healthz`. Trigger a fetch any time with
`make cycle` (own process) or `curl -X POST http://127.0.0.1:8000/cycle`
(running server).

## See a digest in an inbox

The digest defaults target a **local** inbox on port 1025, so nothing real is
sent. With [Mailpit](https://mailpit.axllent.org) (`brew install mailpit`):

```sh
mailpit                 # local inbox, UI at http://localhost:8025
make demo               # sends one guaranteed digest through it
```

`make demo` time-shifts the repo's recorded upstream fixtures so "tonight"
has clear-sky visible passes and runs one real cycle against them — the full
SMTP path, deterministic regardless of actual weather. No Mailpit? The repo
sink works too: `python3 -m tests.smtp_capture 1025` (prints captured mail).

With real data (`make run` / `make cycle` and `SMTP_TO` set in `.env`), you
get at most one email per day, only when the next 24 h hold a go/maybe pass.
Sending real mail is deliberate: point `SMTP_HOST`/`SMTP_PORT` at a real
server and usually set `SMTP_STARTTLS=yes` plus `SMTP_USER`/`SMTP_PASSWORD`.
Secrets live only in the git-ignored `.env`.

## Configuration

Everything comes from the environment; `make run`/`make cycle` source `.env`
automatically. `.env.example` documents every variable with placeholders;
formats and defaults are specified in
[docs/specs/config.md](docs/specs/config.md). Bad configuration fails fast at
startup with one message listing every problem (exit 2) — e.g.
`LATITUDE=banana` yields
`LATITUDE: expected decimal degrees between -90 and 90 (e.g. 47.61), got 'banana'`.
Location is numeric lat/lon only in v1.

## How it decides

A pass is judged from the store each cycle (upstream outages don't blank the
page): **skip** when the ISS isn't visible (daylight/shadow), when it peaks
below `MIN_ELEVATION_DEG` (25°), or when the worst overlapping forecast hour
exceeds `CLOUD_MAYBE_MAX` (70 %); **go** at or under `CLOUD_GO_MAX` (30 %);
**maybe** in between or when no forecast covers the window yet. Rules:
[docs/specs/verdict-digest.md](docs/specs/verdict-digest.md).

## Project layout

- `skywatch/` — the service; `tests/` — offline suite (`make test`)
- `docs/GOAL.md` — goal and milestones; `docs/specs/` — behavior contracts;
  `docs/adr/` — architecture decisions; `docs/log.md` — changelog
