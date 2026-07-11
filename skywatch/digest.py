"""Digest selection and composition (contract: docs/specs/verdict-digest.md).

One plain-text email when the next 24 hours hold a go or maybe pass; the
formatting target is the goal's example line:
"21:42–21:48, max elevation 74°, WSW→ENE, cloud 20% — GO".
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, tzinfo as TzInfo

from skywatch.model import parse_utc
from skywatch.verdict import GO, MAYBE, Verdict

WINDOW_HOURS = 24


def in_quiet_hours(moment: time, start: time, end: time) -> bool:
    """True when the local wall-clock time falls in [start, end); the window
    may cross midnight (22:00-08:00)."""
    if start <= end:
        return start <= moment < end
    return moment >= start or moment < end


def watchable(verdicts: list[Verdict], now: datetime) -> list[Verdict]:
    """Go/maybe verdicts starting within the next WINDOW_HOURS, soonest first."""
    horizon = now + timedelta(hours=WINDOW_HOURS)
    picked = [
        v
        for v in verdicts
        if v.verdict in (GO, MAYBE) and now <= parse_utc(v.pass_.start_utc) < horizon
    ]
    return sorted(picked, key=lambda v: v.pass_.start_utc)


def _local(stamp_utc: str, tz: TzInfo | None) -> datetime:
    return parse_utc(stamp_utc).astimezone(tz)


def compose(
    picked: list[Verdict],
    latitude: float,
    longitude: float,
    tz: TzInfo | None = None,
) -> tuple[str, str]:
    """Subject and body for a non-empty watchable list."""
    if not picked:
        raise ValueError("compose() needs at least one watchable verdict")
    first = picked[0]
    first_start = _local(first.pass_.start_utc, tz)
    count = len(picked)
    plural = "es" if count != 1 else ""
    best = max(v.pass_.max_elevation_deg for v in picked)
    subject = (
        f"ISS tonight: {count} watchable pass{plural}, "
        f"first {first_start:%H:%M} ({first.verdict.upper()}, max {best:.0f}°)"
    )
    lines = [
        f"{count} pass{plural} worth stepping outside for in the next "
        f"{WINDOW_HOURS} hours:",
        "",
    ]
    for v in picked:
        p = v.pass_
        start, end = _local(p.start_utc, tz), _local(p.end_utc, tz)
        cloud = f"cloud {v.cloud_cover_pct}%" if v.cloud_cover_pct is not None else "cloud unknown"
        lines.append(
            f"{start:%a %H:%M}–{end:%H:%M}, max elevation "
            f"{p.max_elevation_deg:.0f}°, {p.start_compass}→{p.end_compass}, "
            f"{cloud} — {v.verdict.upper()}"
        )
        lines.append(f"    {v.reason}")
    lines += [
        "",
        f"Location {latitude:.2f}, {longitude:.2f} — Skywatch",
    ]
    return subject, "\n".join(lines)
