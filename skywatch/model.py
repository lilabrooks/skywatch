"""Normalized domain types and time/compass helpers shared across modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

ISO_Z = "%Y-%m-%dT%H:%M:%SZ"

COMPASS_16 = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_z(moment: datetime) -> str:
    """Aware datetime -> 'YYYY-MM-DDTHH:MM:SSZ' (UTC, second precision)."""
    if moment.tzinfo is None:
        raise ValueError("naive datetime; pass an aware one")
    return moment.astimezone(timezone.utc).strftime(ISO_Z)


def parse_utc(text: str) -> datetime:
    """Parse an ISO 8601 string (Z, offset, space separator, or naive-as-UTC)."""
    moment = datetime.fromisoformat(text.strip())
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def compass_point(azimuth_deg: float) -> str:
    """Azimuth in degrees -> 16-point compass name (e.g. 247.5 -> 'WSW')."""
    return COMPASS_16[round((azimuth_deg % 360) / 22.5) % 16]


@dataclass(frozen=True)
class Pass:
    source: str
    start_utc: str
    culmination_utc: str
    end_utc: str
    max_elevation_deg: float
    start_azimuth_deg: float
    end_azimuth_deg: float
    start_compass: str
    end_compass: str
    visible: bool


@dataclass(frozen=True)
class ForecastHour:
    source: str
    hour_utc: str
    cloud_cover_pct: int
