# Specs

- [Configuration contract](config.md): Environment variables, formats and defaults, and fail-fast startup on bad configuration (all errors collected, exit 2).
- [Source fetch, normalization, and storage contract](sources.md): Upstream fetch and normalization into typed rows, SQLite storage semantics, and per-source failure isolation in the cycle.
- [Verdict and digest contract](verdict-digest.md): Go/maybe/skip rules joining passes to cloud cover, and when exactly one digest email goes out (dedup per local date).
- [Status page contract](status-page.md): Routes and page content — upcoming verdicts with reasons, last-cycle line, empty states — plus escaping and loopback safety rules.
- [Scheduler and operations contract](operations.md): Interval scheduling with crash survival, quiet hours (digest-only), the POST /cycle trigger, and retention pruning.
