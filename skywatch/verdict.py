"""Join passes against cloud cover into go / maybe / skip with reasons.

Pure functions; contract in docs/specs/verdict-digest.md. Cloud cover for a
pass is the worst (max) percentage over the forecast hours the pass touches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping

from skywatch.config import Config
from skywatch.model import Pass, parse_utc, to_utc_z

GO, MAYBE, SKIP = "go", "maybe", "skip"


@dataclass(frozen=True)
class Verdict:
    pass_: Pass
    verdict: str  # go | maybe | skip
    reason: str
    cloud_cover_pct: int | None  # None when no forecast covered the pass


def hours_touched(start_utc: str, end_utc: str) -> list[str]:
    """UTC hour stamps whose hour-long window overlaps [start, end]."""
    start = parse_utc(start_utc).replace(minute=0, second=0, microsecond=0)
    end = parse_utc(end_utc)
    hours = []
    cursor = start
    while cursor <= end:
        hours.append(to_utc_z(cursor))
        cursor += timedelta(hours=1)
    return hours


def worst_cloud_cover(
    start_utc: str, end_utc: str, clouds: Mapping[str, int]
) -> int | None:
    covered = [clouds[h] for h in hours_touched(start_utc, end_utc) if h in clouds]
    return max(covered) if covered else None


def judge_pass(p: Pass, clouds: Mapping[str, int], config: Config) -> Verdict:
    elevation = f"max elevation {p.max_elevation_deg:.0f}°"
    if not p.visible:
        return Verdict(
            p, SKIP, "not visible (daylight, or the ISS sits in Earth's shadow)", None
        )
    if p.max_elevation_deg < config.min_elevation_deg:
        return Verdict(
            p,
            SKIP,
            f"too low: {elevation}, below your {config.min_elevation_deg:.0f}° minimum",
            worst_cloud_cover(p.start_utc, p.end_utc, clouds),
        )
    cloud = worst_cloud_cover(p.start_utc, p.end_utc, clouds)
    if cloud is None:
        return Verdict(p, MAYBE, f"no cloud forecast for this window yet; {elevation}", None)
    if cloud <= config.cloud_go_max:
        return Verdict(p, GO, f"cloud {cloud}%, {elevation} — clear and high", cloud)
    if cloud <= config.cloud_maybe_max:
        return Verdict(p, MAYBE, f"cloud {cloud}% — could break either way; {elevation}", cloud)
    return Verdict(p, SKIP, f"cloud {cloud}% — overcast", cloud)


def judge(passes: list[Pass], clouds: Mapping[str, int], config: Config) -> list[Verdict]:
    return [judge_pass(p, clouds, config) for p in passes]
