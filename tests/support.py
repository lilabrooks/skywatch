"""Shared test helpers and fixture loading."""

import json
from pathlib import Path

from skywatch.config import Config
from skywatch.model import Pass

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


def make_config(**overrides) -> Config:
    values = {"latitude": 47.61, "longitude": -122.33, "port": 8000, "db_path": ":memory:"}
    values.update(overrides)
    return Config(**values)


def make_pass(**overrides) -> Pass:
    values = {
        "source": "sat.terrestre.ar",
        "start_utc": "2026-07-11T03:06:46Z",
        "culmination_utc": "2026-07-11T03:08:50Z",
        "end_utc": "2026-07-11T03:10:54Z",
        "max_elevation_deg": 15.3,
        "start_azimuth_deg": 173.37,
        "end_azimuth_deg": 98.01,
        "start_compass": "S",
        "end_compass": "E",
        "visible": False,
    }
    values.update(overrides)
    return Pass(**values)
