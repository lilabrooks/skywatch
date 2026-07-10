# Skywatch

A local always-on service that emails you a digest when tonight's ISS pass is
worth stepping outside for. It fetches pass predictions and the cloud-cover
forecast for your location, joins them into go / maybe / skip verdicts with
reasons, keeps history in SQLite, and serves a small status page.

Under construction, milestone by milestone — see [docs/GOAL.md](docs/GOAL.md).

## Quickstart

Requires Python 3.12+ and `make`. No packages to install.

```sh
cp .env.example .env   # then set your latitude/longitude
make test              # offline test suite, no network or credentials
make run               # http://127.0.0.1:8000 — health check at /healthz
```

Decisions live in [docs/adr/](docs/adr/), contracts in [docs/specs/](docs/specs/),
and the changelog in [docs/log.md](docs/log.md).
