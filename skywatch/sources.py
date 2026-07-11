"""Upstream URL builders and normalizers (contract: docs/specs/sources.md).

Sources chosen in ADR-0002: ISS passes from sat.terrestre.ar, hourly cloud
cover from Open-Meteo. Normalizers turn upstream quirks into typed rows and
raise SourceError on any shape surprise; they never let a KeyError escape.
"""

from __future__ import annotations

import urllib.parse
from typing import Callable

from skywatch.config import Config
from skywatch.model import ForecastHour, Pass, compass_point, parse_utc, to_utc_z

FetchJson = Callable[[str], object]

PASSES_SOURCE = "sat.terrestre.ar"
PASS_LIMIT = 10

FORECAST_SOURCE = "open-meteo"
FORECAST_DAYS = 2


class SourceError(Exception):
    """The upstream answered, but not in the shape this contract expects."""


def passes_url(config: Config) -> str:
    query = urllib.parse.urlencode(
        {"lat": config.latitude, "lon": config.longitude, "limit": PASS_LIMIT}
    )
    return f"{config.passes_base_url}?{query}"


def forecast_url(config: Config) -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": config.latitude,
            "longitude": config.longitude,
            "hourly": "cloud_cover",
            "timezone": "UTC",
            "forecast_days": FORECAST_DAYS,
        }
    )
    return f"{config.forecast_base_url}?{query}"


def fetch_passes(fetch_json: FetchJson, config: Config) -> list[Pass]:
    return normalize_passes(fetch_json(passes_url(config)))


def fetch_forecast(fetch_json: FetchJson, config: Config) -> list[ForecastHour]:
    return normalize_forecast(fetch_json(forecast_url(config)))


def normalize_passes(payload: object) -> list[Pass]:
    if not isinstance(payload, list):
        raise SourceError(f"passes: expected a JSON list, got {type(payload).__name__}")
    passes = []
    for index, item in enumerate(payload):
        try:
            rise, culmination, set_ = item["rise"], item["culmination"], item["set"]
            start_az = float(rise["az"])
            end_az = float(set_["az"])
            passes.append(
                Pass(
                    source=PASSES_SOURCE,
                    start_utc=to_utc_z(parse_utc(rise["utc_datetime"])),
                    culmination_utc=to_utc_z(parse_utc(culmination["utc_datetime"])),
                    end_utc=to_utc_z(parse_utc(set_["utc_datetime"])),
                    max_elevation_deg=float(culmination["alt"]),
                    start_azimuth_deg=start_az,
                    end_azimuth_deg=end_az,
                    start_compass=compass_point(start_az),
                    end_compass=compass_point(end_az),
                    visible=bool(item["visible"]),
                )
            )
        except (KeyError, TypeError, ValueError) as err:
            raise SourceError(f"passes: item {index} malformed: {err!r}") from err
    return sorted(passes, key=lambda p: p.start_utc)


def normalize_forecast(payload: object) -> list[ForecastHour]:
    try:
        hourly = payload["hourly"]  # type: ignore[index]
        times, cover = hourly["time"], hourly["cloud_cover"]
    except (KeyError, TypeError) as err:
        raise SourceError(f"forecast: missing hourly time/cloud_cover: {err!r}") from err
    if not isinstance(times, list) or not isinstance(cover, list) or len(times) != len(cover):
        raise SourceError(
            f"forecast: time/cloud_cover must be lists of equal length "
            f"(got {len(times) if isinstance(times, list) else '?'} / "
            f"{len(cover) if isinstance(cover, list) else '?'})"
        )
    hours = []
    for index, (stamp, value) in enumerate(zip(times, cover)):
        try:
            percent = min(100, max(0, round(float(value))))
            hours.append(
                ForecastHour(
                    source=FORECAST_SOURCE,
                    hour_utc=to_utc_z(parse_utc(stamp)),  # requested with timezone=UTC
                    cloud_cover_pct=percent,
                )
            )
        except (TypeError, ValueError) as err:
            raise SourceError(f"forecast: hour {index} malformed: {err!r}") from err
    return hours
