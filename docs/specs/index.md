# Specs

- [Configuration contract](config.md): Environment variables, formats and defaults, and fail-fast startup on bad configuration (all errors collected, exit 2).
- [Source fetch, normalization, and storage contract](sources.md): Upstream fetch and normalization into typed rows, SQLite storage semantics, and per-source failure isolation in the cycle.
- [Verdict and digest contract](verdict-digest.md): Go/maybe/skip rules joining passes to cloud cover, and when exactly one digest email goes out (dedup per local date).
