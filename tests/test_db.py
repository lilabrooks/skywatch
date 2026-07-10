import tempfile
import unittest
from pathlib import Path

from skywatch import db
from skywatch.model import ForecastHour
from tests.support import make_pass


class MigrationTests(unittest.TestCase):
    def test_fresh_file_migrates_to_latest_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "skywatch.db")
            conn = db.connect(path)
            try:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, len(db.MIGRATIONS))
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                self.assertEqual(mode, "wal")
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertLessEqual({"passes", "forecast_hours", "cycles"}, tables)
            finally:
                conn.close()

    def test_reconnect_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "skywatch.db")
            db.connect(path).close()
            conn = db.connect(path)  # must not fail re-applying migrations
            conn.close()


class PassStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)

    def counts(self):
        return [
            row["start_utc"]
            for row in self.conn.execute("SELECT start_utc FROM passes ORDER BY start_utc")
        ]

    def test_replace_future_keeps_history_and_swaps_future(self):
        now = "2026-07-10T12:00:00Z"
        past = make_pass(start_utc="2026-07-09T03:00:00Z")
        stale_future = make_pass(start_utc="2026-07-15T03:00:00Z")
        db.replace_future_passes(
            self.conn, past.source, "2026-07-01T00:00:00Z", [past], now
        )
        db.replace_future_passes(
            self.conn, past.source, "2026-07-10T00:00:00Z", [stale_future], now
        )
        fresh = make_pass(start_utc="2026-07-11T03:06:46Z")
        db.replace_future_passes(self.conn, past.source, now, [fresh], now)
        self.assertEqual(
            self.counts(), ["2026-07-09T03:00:00Z", "2026-07-11T03:06:46Z"]
        )

    def test_replace_is_idempotent(self):
        now = "2026-07-10T12:00:00Z"
        rows = [make_pass(), make_pass(start_utc="2026-07-11T04:41:48Z")]
        db.replace_future_passes(self.conn, rows[0].source, now, rows, now)
        db.replace_future_passes(self.conn, rows[0].source, now, rows, now)
        self.assertEqual(len(self.counts()), 2)

    def test_pass_row_roundtrip(self):
        now = "2026-07-10T12:00:00Z"
        db.replace_future_passes(self.conn, "sat.terrestre.ar", now, [make_pass()], now)
        row = self.conn.execute("SELECT * FROM passes").fetchone()
        self.assertEqual(row["start_compass"], "S")
        self.assertEqual(row["max_elevation_deg"], 15.3)
        self.assertEqual(row["visible"], 0)
        self.assertEqual(row["fetched_at_utc"], now)


class ForecastStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)

    def test_upsert_latest_wins(self):
        hour = "2026-07-10T21:00:00Z"
        first = ForecastHour(source="open-meteo", hour_utc=hour, cloud_cover_pct=80)
        second = ForecastHour(source="open-meteo", hour_utc=hour, cloud_cover_pct=20)
        db.upsert_forecast_hours(self.conn, [first], "2026-07-10T10:00:00Z")
        db.upsert_forecast_hours(self.conn, [second], "2026-07-10T18:00:00Z")
        rows = self.conn.execute("SELECT * FROM forecast_hours").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cloud_cover_pct"], 20)
        self.assertEqual(rows[0]["fetched_at_utc"], "2026-07-10T18:00:00Z")


class CycleAuditTests(unittest.TestCase):
    def test_start_and_finish_cycle(self):
        conn = db.connect(":memory:")
        self.addCleanup(conn.close)
        cycle_id = db.start_cycle(conn, "2026-07-10T12:00:00Z")
        db.finish_cycle(conn, cycle_id, "2026-07-10T12:00:03Z", "ok: 8 passes", "error: boom")
        row = conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()
        self.assertEqual(row["passes_status"], "ok: 8 passes")
        self.assertEqual(row["forecast_status"], "error: boom")
        self.assertEqual(row["finished_at_utc"], "2026-07-10T12:00:03Z")


if __name__ == "__main__":
    unittest.main()
