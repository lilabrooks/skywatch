import unittest

from skywatch.model import ForecastHour
from skywatch.sources import (
    SourceError,
    forecast_url,
    normalize_forecast,
    normalize_passes,
    passes_url,
)
from tests.support import load_fixture, make_config


class PassesNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.payload = load_fixture("terrestre_passes.json")

    def test_recorded_fixture_normalizes(self):
        passes = normalize_passes(self.payload)
        self.assertEqual(len(passes), 8)
        self.assertEqual(sum(1 for p in passes if p.visible), 5)
        self.assertEqual([p.start_utc for p in passes], sorted(p.start_utc for p in passes))

    def test_first_pass_fields(self):
        first = normalize_passes(self.payload)[0]
        self.assertEqual(first.source, "sat.terrestre.ar")
        self.assertEqual(first.start_utc, "2026-07-11T03:06:46Z")
        self.assertEqual(first.end_utc, "2026-07-11T03:10:54Z")
        self.assertEqual(first.max_elevation_deg, 15.3)
        self.assertEqual(first.start_azimuth_deg, 173.37)
        self.assertEqual(first.start_compass, "S")
        self.assertEqual(first.end_compass, "E")
        self.assertFalse(first.visible)

    def test_last_pass_compass_and_visibility(self):
        last = normalize_passes(self.payload)[-1]
        self.assertEqual(last.start_compass, "WNW")  # az 294.30
        self.assertEqual(last.end_compass, "E")  # az 82.15
        self.assertTrue(last.visible)

    def test_not_a_list_rejected(self):
        with self.assertRaises(SourceError):
            normalize_passes({"passes": []})

    def test_missing_key_rejected_with_index(self):
        broken = [dict(self.payload[0])]
        del broken[0]["culmination"]
        with self.assertRaises(SourceError) as ctx:
            normalize_passes(broken)
        self.assertIn("item 0", str(ctx.exception))

    def test_non_numeric_azimuth_rejected(self):
        broken = [dict(self.payload[0])]
        broken[0]["rise"] = {**broken[0]["rise"], "az": "north-ish"}
        with self.assertRaises(SourceError):
            normalize_passes(broken)

    def test_url_contains_location(self):
        url = passes_url(make_config())
        self.assertIn("lat=47.61", url)
        self.assertIn("lon=-122.33", url)
        self.assertTrue(url.startswith("https://sat.terrestre.ar/passes/25544?"))

    def test_url_base_overridable_for_local_fixtures(self):
        config = make_config(passes_base_url="http://127.0.0.1:9999/passes.json")
        self.assertTrue(passes_url(config).startswith("http://127.0.0.1:9999/passes.json?"))


class ForecastNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.payload = load_fixture("open_meteo_cloud_cover.json")

    def test_recorded_fixture_normalizes(self):
        hours = normalize_forecast(self.payload)
        self.assertEqual(len(hours), 48)
        self.assertEqual(
            hours[0],
            ForecastHour(source="open-meteo", hour_utc="2026-07-10T00:00:00Z", cloud_cover_pct=0),
        )
        self.assertEqual(hours[-1].hour_utc, "2026-07-11T23:00:00Z")
        self.assertEqual(hours[-1].cloud_cover_pct, 48)
        self.assertTrue(all(0 <= h.cloud_cover_pct <= 100 for h in hours))

    def test_missing_hourly_rejected(self):
        with self.assertRaises(SourceError):
            normalize_forecast({"latitude": 47.61})

    def test_mismatched_arrays_rejected(self):
        with self.assertRaises(SourceError):
            normalize_forecast({"hourly": {"time": ["2026-07-10T00:00"], "cloud_cover": []}})

    def test_non_numeric_cover_rejected(self):
        payload = {"hourly": {"time": ["2026-07-10T00:00"], "cloud_cover": ["dense"]}}
        with self.assertRaises(SourceError) as ctx:
            normalize_forecast(payload)
        self.assertIn("hour 0", str(ctx.exception))

    def test_out_of_range_cover_clamped(self):
        payload = {"hourly": {"time": ["2026-07-10T00:00"], "cloud_cover": [104.2]}}
        self.assertEqual(normalize_forecast(payload)[0].cloud_cover_pct, 100)

    def test_url_requests_utc_hourly_cloud_cover(self):
        url = forecast_url(make_config())
        self.assertIn("hourly=cloud_cover", url)
        self.assertIn("timezone=UTC", url)
        self.assertIn("latitude=47.61", url)


if __name__ == "__main__":
    unittest.main()
