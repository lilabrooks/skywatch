---
type: ADR
title: ISS pass and cloud-cover upstream APIs
description: Passes from sat.terrestre.ar (keyless, visibility-aware), hourly cloud cover from Open-Meteo (keyless); per-source failure isolation in the cycle.
tags: [adr]
timestamp: 2026-07-10T23:49:31Z
status: proposed
---

# Status

Proposed (authored per the decision policy; awaiting owner review)

# Context

The goal requires two external sources over public HTTP APIs: ISS pass
predictions and hourly cloud cover for a configured lat/lon. The digest promises
*visible* passes ("worth stepping outside"), so a pass source that only lists
radio passes would mark useless daytime passes as GO. Everything must be
mockable offline; both endpoints were probed live on 2026-07-10 and their real
responses recorded as fixtures under `tests/fixtures/`.

# Decision

- **Passes**: `GET https://sat.terrestre.ar/passes/25544?lat=…&lon=…&limit=…`
  (the open-source `satellite-passes-api`, skyfield-based, no key). It returns
  rise/culmination/set with altitude, azimuth (degrees and octant), timestamps,
  and — decisively — per-pass `visible` (observer in darkness while the ISS is
  sunlit), which is exactly the goal's "visible pass" condition.
- **Cloud cover**: `GET https://api.open-meteo.com/v1/forecast?latitude=…&longitude=…&hourly=cloud_cover&timezone=UTC&forecast_days=2`
  (keyless, free for non-commercial, stable JSON: parallel `time[]` /
  `cloud_cover[]` arrays in percent).
- Both are fetched with explicit timeouts through the injectable fetch layer;
  each source fails independently and a failure never aborts the other source
  or the cycle (details in `docs/specs/sources.md`).
- Normalization strips upstream quirks at the boundary: string-encoded numbers
  and spaced ISO timestamps from terrestre become typed values and UTC `…Z`
  strings; compass points are derived from azimuth degrees.

# Alternatives considered

- **api.g7vrd.co.uk satellite passes** (keyless): clean shape, but radio passes
  only — no visibility or sunlit data, so most flagged passes would be
  unwatchable daytime events; also self-labels `api_status: ALPHA`.
- **N2YO `visualpasses`**: visibility-filtered *and* includes brightness
  (magnitude), which the verdict quality ideally wants — but it requires a
  registered API key. That adds an operator signup step and a credential, and
  fixtures could not even be recorded without creating an account. Noted as the
  natural upgrade if the owner wants magnitude-based quality (see revisit).
- **Open Notify pass endpoint**: retired; dead.
- **Local propagation from TLEs** (sgp4/skyfield): removes the hobby-API
  availability risk but adds a real dependency plus orbital/visibility math,
  against ADR-0001; overkill for v1.
- **Weather alternatives** (NWS api.weather.gov, MET Norway): both credible and
  keyless, but US-only coverage (NWS) or stricter User-Agent/terms (MET);
  Open-Meteo has the simplest hourly cloud-cover contract worldwide.

# Consequences

- No brightness/magnitude in v1: verdict quality (milestone 3) rests on max
  elevation plus the upstream `visible` flag. The goal's "elevation/brightness"
  quality is satisfied on elevation; brightness needs the N2YO upgrade path.
- Both upstreams are free/hobby-grade services; outages are expected and must
  stay non-fatal. Stored predictions keep serving the page and digest between
  successful fetches. Request cadence stays low (scheduler interval is hours,
  landing in milestone 5).
- Upstream shape changes surface as normalizer errors recorded on the cycle,
  not crashes; fixtures pin the shapes we depend on.

# Rollback / revisit trigger

Revisit via a new ADR if: sat.terrestre.ar goes away, rate-limits us, or
changes shape (swap in N2YO with an owner-provided key, or another predictor —
the normalizer boundary keeps the blast radius to `skywatch/sources.py` plus
fixtures); the owner wants magnitude-based quality (N2YO); or Open-Meteo terms
or availability change (NWS/MET behind the same normalizer). Rolling back a
source choice means replacing one builder+normalizer pair and its fixtures.
