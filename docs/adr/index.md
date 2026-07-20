# ADRs

- [0001 Python standard-library-only runtime stack](0001-python-stdlib-stack.md): Python 3.12+ with zero third-party runtime deps — stdlib http.server, urllib, sqlite3, smtplib, threading, unittest; make as command runner.
- [0002 ISS pass and cloud-cover upstream APIs](0002-pass-and-weather-sources.md): Passes from sat.terrestre.ar (keyless, visibility-aware), cloud cover from Open-Meteo (keyless); per-source failure isolation.
- [0003 SQLite persistence layout and migrations](0003-sqlite-persistence.md): Single DB_PATH file, WAL, user_version migrations in code; passes replaced-from-now, forecasts upserted, cycles audited.
- [0004 SMTP digest transport, gating, and test layers](0004-smtp-digest-transport.md): smtplib behind a Notifier seam; env-only credentials (repr-safe), default port 1025 targets a local sink so real sends are owner-deliberate; four test layers.
- [0005 GitHub Actions CI](0005-github-actions-ci.md): Read-only workflow runs the offline suite on Python 3.12-3.14 and checks OKF mapping freshness on pull requests and main. (accepted)
