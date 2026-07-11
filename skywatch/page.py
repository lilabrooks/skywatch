"""Status page rendering (contract: docs/specs/status-page.md).

Pure string building from store rows — no template engine (ADR-0001). Every
dynamic value goes through html.escape; verdict CSS classes come from a
whitelist, never from data.
"""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime, tzinfo as TzInfo

from skywatch import db
from skywatch import __version__
from skywatch.config import Config
from skywatch.model import parse_utc, to_utc_z

VERDICT_CLASSES = {"go", "maybe", "skip"}

STYLESHEET = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0 auto; max-width: 60rem; padding: 1.5rem;
}
header h1 { margin: 0; font-size: 1.6rem; }
header .sub, footer { color: color-mix(in srgb, currentColor 60%, transparent); }
.cycle {
  margin: 1rem 0; padding: .6rem .9rem; border-radius: .5rem;
  background: color-mix(in srgb, currentColor 8%, transparent);
  font-size: .95rem;
}
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: .45rem .6rem; vertical-align: top; }
tbody tr { border-top: 1px solid color-mix(in srgb, currentColor 15%, transparent); }
.badge {
  display: inline-block; padding: .1rem .55rem; border-radius: 999px;
  font-size: .8rem; font-weight: 700; text-transform: uppercase;
  background: color-mix(in srgb, currentColor 15%, transparent);
}
.badge.go { background: #1a7f37; color: #fff; }
.badge.maybe { background: #b58a00; color: #fff; }
.badge.skip { opacity: .65; }
.reason { color: color-mix(in srgb, currentColor 70%, transparent); font-size: .9rem; }
.empty { padding: 2rem 0; }
.empty code { background: color-mix(in srgb, currentColor 10%, transparent); padding: .1rem .3rem; }
footer { margin-top: 2rem; font-size: .85rem; }
"""


def _local(stamp_utc: str, tz: TzInfo | None) -> datetime:
    return parse_utc(stamp_utc).astimezone(tz)


def _cycle_line(cycle: sqlite3.Row | None, tz: TzInfo | None) -> str:
    if cycle is None:
        return "<section class='cycle'>No cycle has run yet.</section>"
    stamp = _local(cycle["started_at_utc"], tz).strftime("%Y-%m-%d %H:%M %Z")
    parts = " · ".join(
        f"{name} {html.escape(str(cycle[key]))}"
        for name, key in (
            ("passes", "passes_status"),
            ("forecast", "forecast_status"),
            ("digest", "digest_status"),
        )
    )
    return f"<section class='cycle'>Last cycle {html.escape(stamp)} — {parts}</section>"


def _verdict_rows(verdicts: list[sqlite3.Row], tz: TzInfo | None) -> str:
    rows = []
    for v in verdicts:
        start, end = _local(v["start_utc"], tz), _local(v["end_utc"], tz)
        window = f"{start:%a %Y-%m-%d %H:%M}–{end:%H:%M}"
        cloud = "—" if v["cloud_cover_pct"] is None else f"{v['cloud_cover_pct']}%"
        verdict = str(v["verdict"])
        badge_class = f"badge {verdict}" if verdict in VERDICT_CLASSES else "badge"
        rows.append(
            "<tr>"
            f"<td>{html.escape(window)}</td>"
            f"<td>{v['max_elevation_deg']:.0f}°</td>"
            f"<td>{html.escape(v['start_compass'])}→{html.escape(v['end_compass'])}</td>"
            f"<td>{html.escape(cloud)}</td>"
            f"<td><span class='{badge_class}'>{html.escape(verdict)}</span></td>"
            f"<td class='reason'>{html.escape(v['reason'])}</td>"
            "</tr>"
        )
    return "".join(rows)


def render(config: Config, conn: sqlite3.Connection, now: datetime, tz: TzInfo | None = None) -> str:
    cycle = db.latest_cycle(conn)
    verdicts = db.latest_verdicts(conn, to_utc_z(now)) if cycle is not None else []

    if cycle is None:
        main = (
            "<div class='empty'><p>No data yet — the first cycle hasn't run.</p>"
            "<p>Trigger one with <code>make cycle</code>, or wait for the scheduler.</p></div>"
        )
    elif not verdicts:
        main = (
            "<div class='empty'><p>No upcoming passes in the store right now.</p>"
            "<p>New predictions arrive with the next cycle.</p></div>"
        )
    else:
        main = (
            "<table><thead><tr>"
            "<th>When</th><th>Max&nbsp;elev.</th><th>Path</th><th>Cloud</th>"
            "<th>Verdict</th><th>Why</th>"
            "</tr></thead><tbody>"
            + _verdict_rows(verdicts, tz)
            + "</tbody></table>"
        )

    location = f"{config.latitude:.2f}, {config.longitude:.2f}"
    return (
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Skywatch</title><link rel='stylesheet' href='/style.css'></head><body>"
        f"<header><h1>Skywatch</h1><p class='sub'>ISS passes × cloud cover for "
        f"{html.escape(location)}</p></header>"
        + _cycle_line(cycle, tz)
        + "<main><h2>Upcoming passes</h2>" + main + "</main>"
        f"<footer>Skywatch {html.escape(__version__)} · sources: sat.terrestre.ar "
        "&amp; open-meteo · health: <a href='/healthz'>/healthz</a></footer>"
        "</body></html>"
    )
