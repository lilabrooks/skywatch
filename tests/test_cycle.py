"""The milestone-2 contract: a triggered cycle against mocks writes source rows,
and timeout/upstream-error/shape fixtures are survived per source."""

import unittest
from datetime import datetime, timezone

from skywatch import db
from skywatch.cycle import run_cycle
from skywatch.fetch import FetchError
from tests.support import load_fixture, make_config, make_pass

FIXED_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def fixed_clock():
    return FIXED_NOW


def fake_fetch(passes="fixture", forecast="fixture"):
    """Returns a fetch_json fake; pass an Exception instance to simulate failure."""
    payloads = {
        "sat.terrestre.ar": load_fixture("terrestre_passes.json") if passes == "fixture" else passes,
        "open-meteo": load_fixture("open_meteo_cloud_cover.json") if forecast == "fixture" else forecast,
    }

    def fetch_json(url):
        for marker, payload in payloads.items():
            if marker in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f"unexpected URL fetched: {url}")

    return fetch_json


class RunCycleTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.config = make_config()

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    def cycle_row(self, cycle_id):
        return self.conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()

    def test_happy_cycle_writes_source_rows(self):
        result = run_cycle(self.conn, self.config, fake_fetch(), fixed_clock)
        self.assertEqual(self.count("passes"), 8)
        self.assertEqual(self.count("forecast_hours"), 48)
        self.assertEqual(result.passes_status, "ok: 8 passes")
        self.assertEqual(result.forecast_status, "ok: 48 hours")
        self.assertTrue(result.ok)
        row = self.cycle_row(result.cycle_id)
        self.assertEqual(row["started_at_utc"], "2026-07-10T12:00:00Z")
        self.assertIsNotNone(row["finished_at_utc"])

    def test_repeat_cycle_does_not_duplicate(self):
        run_cycle(self.conn, self.config, fake_fetch(), fixed_clock)
        run_cycle(self.conn, self.config, fake_fetch(), fixed_clock)
        self.assertEqual(self.count("passes"), 8)
        self.assertEqual(self.count("forecast_hours"), 48)
        self.assertEqual(self.count("cycles"), 2)

    def test_passes_timeout_survived_and_keeps_stored_predictions(self):
        seeded = make_pass(start_utc="2026-07-11T03:06:46Z")
        db.replace_future_passes(
            self.conn, seeded.source, "2026-07-10T00:00:00Z", [seeded], "2026-07-10T00:00:00Z"
        )
        result = run_cycle(
            self.conn,
            self.config,
            fake_fetch(passes=FetchError("timed out after 10s: https://sat.terrestre.ar/...")),
            fixed_clock,
        )
        self.assertFalse(result.ok)
        self.assertIn("timed out", result.passes_status)
        self.assertEqual(self.count("passes"), 1, "stored prediction must survive the outage")
        self.assertEqual(self.count("forecast_hours"), 48, "other source still runs")
        self.assertIn("error", self.cycle_row(result.cycle_id)["passes_status"])

    def test_upstream_http_error_survived(self):
        result = run_cycle(
            self.conn,
            self.config,
            fake_fetch(forecast=FetchError("HTTP 500 from https://api.open-meteo.com/...")),
            fixed_clock,
        )
        self.assertEqual(self.count("passes"), 8)
        self.assertEqual(self.count("forecast_hours"), 0)
        self.assertIn("HTTP 500", result.forecast_status)

    def test_malformed_shape_survived(self):
        result = run_cycle(
            self.conn,
            self.config,
            fake_fetch(passes={"unexpected": "shape"}),
            fixed_clock,
        )
        self.assertIn("error", result.passes_status)
        self.assertEqual(self.count("forecast_hours"), 48)

    def test_both_sources_failing_still_finishes_cycle(self):
        result = run_cycle(
            self.conn,
            self.config,
            fake_fetch(passes=FetchError("down"), forecast=FetchError("down")),
            fixed_clock,
        )
        row = self.cycle_row(result.cycle_id)
        self.assertIsNotNone(row["finished_at_utc"])
        self.assertIn("error", row["passes_status"])
        self.assertIn("error", row["forecast_status"])


if __name__ == "__main__":
    unittest.main()
