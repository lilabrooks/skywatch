"""Cycle contracts: a triggered cycle against mocks writes source rows,
timeout/upstream-error/shape fixtures are survived per source (milestone 2),
and the digest goes out exactly once on the go fixture, never on the cloudy
one (milestone 3)."""

import unittest
from datetime import datetime, timezone

from skywatch import db
from skywatch.config import SmtpConfig
from skywatch.cycle import run_cycle
from skywatch.fetch import FetchError
from skywatch.notify import SMTPNotifier
from tests.smtp_capture import SMTPCaptureServer
from tests.support import (
    FailingNotifier,
    RecordingNotifier,
    load_fixture,
    make_config,
    make_pass,
)

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

    def test_outage_cycle_still_judges_from_stored_data(self):
        run_cycle(self.conn, self.config, fake_fetch(), fixed_clock)
        result = run_cycle(
            self.conn,
            self.config,
            fake_fetch(passes=FetchError("down"), forecast=FetchError("down")),
            fixed_clock,
        )
        self.assertEqual(result.verdict_count, 8, "verdicts must come from the store")


def clear_fetch():
    return fake_fetch(forecast=load_fixture("open_meteo_cloud_cover_clear.json"))


class DigestCycleTests(unittest.TestCase):
    """The recorded forecast fixture is genuinely overcast during every
    visible pass (53-100% cloud), so recorded = cloudy case; the derived
    clear-sky variant (5% everywhere) is the go case."""

    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.config = make_config()

    def digests(self):
        return self.conn.execute("SELECT * FROM digests").fetchall()

    def test_go_fixture_sends_exactly_one_digest(self):
        notifier = RecordingNotifier()
        result = run_cycle(
            self.conn, self.config, clear_fetch(), fixed_clock, notifier, timezone.utc
        )
        self.assertTrue(result.digest_status.startswith("sent:"), result.digest_status)
        self.assertEqual(len(notifier.sent), 1)
        subject, body = notifier.sent[0]
        self.assertIn("ISS tonight", subject)
        self.assertIn("— GO", body)
        rows = self.digests()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["local_date"], "2026-07-10")

    def test_repeat_cycle_same_day_does_not_resend(self):
        notifier = RecordingNotifier()
        run_cycle(self.conn, self.config, clear_fetch(), fixed_clock, notifier, timezone.utc)
        result = run_cycle(
            self.conn, self.config, clear_fetch(), fixed_clock, notifier, timezone.utc
        )
        self.assertEqual(result.digest_status, "skipped: already sent for 2026-07-10")
        self.assertEqual(len(notifier.sent), 1)

    def test_cloudy_fixture_sends_nothing(self):
        notifier = RecordingNotifier()
        result = run_cycle(
            self.conn, self.config, fake_fetch(), fixed_clock, notifier, timezone.utc
        )
        self.assertEqual(result.digest_status, "skipped: no watchable pass in the next 24h")
        self.assertEqual(notifier.sent, [])
        self.assertEqual(self.digests(), [])

    def test_no_notifier_records_unconfigured_smtp(self):
        result = run_cycle(
            self.conn, self.config, clear_fetch(), fixed_clock, None, timezone.utc
        )
        self.assertEqual(result.digest_status, "skipped: SMTP not configured")
        self.assertEqual(self.digests(), [])

    def test_transport_failure_recorded_and_retried_next_cycle(self):
        result = run_cycle(
            self.conn, self.config, clear_fetch(), fixed_clock, FailingNotifier(), timezone.utc
        )
        self.assertTrue(result.digest_status.startswith("error:"), result.digest_status)
        self.assertEqual(self.digests(), [], "failed send must not mark the day done")
        notifier = RecordingNotifier()
        retry = run_cycle(
            self.conn, self.config, clear_fetch(), fixed_clock, notifier, timezone.utc
        )
        self.assertTrue(retry.digest_status.startswith("sent:"))
        self.assertEqual(len(notifier.sent), 1)

    def test_verdicts_persisted_for_every_future_pass(self):
        result = run_cycle(
            self.conn, self.config, clear_fetch(), fixed_clock, None, timezone.utc
        )
        rows = self.conn.execute(
            "SELECT verdict, cycle_id, start_utc FROM verdicts ORDER BY start_utc"
        ).fetchall()
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["cycle_id"] == result.cycle_id for row in rows))
        # Clear fixture: visible+high passes go, low/invisible ones skip, and
        # the two passes starting beyond the 48h forecast horizon are maybe
        # ("no cloud forecast for this window yet").
        by_verdict = {}
        for row in rows:
            by_verdict.setdefault(row["verdict"], []).append(row)
        self.assertIn("go", by_verdict)
        self.assertIn("skip", by_verdict)
        self.assertTrue(
            all(row["start_utc"] >= "2026-07-12T00:00:00Z" for row in by_verdict.get("maybe", [])),
            "maybe is only for passes beyond the forecast horizon",
        )


class LoopbackSMTPCycleTests(unittest.TestCase):
    """Milestone-3 verification, literally: real SMTPNotifier over a real
    loopback socket — one send for the go fixture, zero for the cloudy one."""

    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.config = make_config()

    def notifier(self, capture):
        return SMTPNotifier(
            SmtpConfig(
                host="127.0.0.1",
                port=capture.port,
                sender="skywatch@localhost",
                recipient="owner@example.org",
            )
        )

    def test_go_fixture_delivers_exactly_one_email(self):
        with SMTPCaptureServer() as capture:
            run_cycle(
                self.conn, self.config, clear_fetch(), fixed_clock,
                self.notifier(capture), timezone.utc,
            )
            self.assertEqual(len(capture.messages), 1)
            message = capture.messages[0].message
            self.assertIn("ISS tonight", message["Subject"])
            self.assertIn("— GO", message.get_content())

    def test_cloudy_fixture_delivers_nothing(self):
        with SMTPCaptureServer() as capture:
            run_cycle(
                self.conn, self.config, fake_fetch(), fixed_clock,
                self.notifier(capture), timezone.utc,
            )
            self.assertEqual(capture.messages, [])


if __name__ == "__main__":
    unittest.main()
