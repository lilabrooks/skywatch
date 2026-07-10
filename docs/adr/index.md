# ADRs

- [0001 Python standard-library-only runtime stack](0001-python-stdlib-stack.md): Python 3.12+ with zero third-party runtime deps — stdlib http.server, urllib, sqlite3, smtplib, threading, unittest; make as command runner. (proposed)
- [0002 ISS pass and cloud-cover upstream APIs](0002-pass-and-weather-sources.md): Passes from sat.terrestre.ar (keyless, visibility-aware), cloud cover from Open-Meteo (keyless); per-source failure isolation. (proposed)
- [0003 SQLite persistence layout and migrations](0003-sqlite-persistence.md): Single DB_PATH file, WAL, user_version migrations in code; passes replaced-from-now, forecasts upserted, cycles audited. (proposed)
