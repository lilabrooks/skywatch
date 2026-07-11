import unittest
from datetime import datetime, time, timezone

from skywatch.digest import compose, in_quiet_hours, watchable
from skywatch.verdict import Verdict
from tests.support import make_pass

NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def verdict_at(start, verdict="go", cloud=5, **pass_overrides):
    p = make_pass(
        visible=True,
        start_utc=start,
        culmination_utc=start,
        end_utc=start.replace("T04:41", "T04:48") if "T04:41" in start else start,
        **pass_overrides,
    )
    return Verdict(p, verdict, "test reason", cloud)


class WatchableTests(unittest.TestCase):
    def test_keeps_go_and_maybe_drops_skip(self):
        verdicts = [
            verdict_at("2026-07-11T04:41:48Z", "go"),
            verdict_at("2026-07-11T06:18:56Z", "maybe"),
            verdict_at("2026-07-11T08:00:00Z", "skip"),
        ]
        picked = watchable(verdicts, NOW)
        self.assertEqual([v.verdict for v in picked], ["go", "maybe"])

    def test_drops_passes_beyond_24h_and_in_the_past(self):
        verdicts = [
            verdict_at("2026-07-09T04:00:00Z", "go"),  # past
            verdict_at("2026-07-11T04:41:48Z", "go"),  # tonight
            verdict_at("2026-07-12T04:00:00Z", "go"),  # beyond horizon
        ]
        picked = watchable(verdicts, NOW)
        self.assertEqual([v.pass_.start_utc for v in picked], ["2026-07-11T04:41:48Z"])

    def test_sorted_soonest_first(self):
        verdicts = [
            verdict_at("2026-07-11T06:18:56Z", "maybe"),
            verdict_at("2026-07-11T04:41:48Z", "go"),
        ]
        picked = watchable(verdicts, NOW)
        self.assertEqual(
            [v.pass_.start_utc for v in picked],
            ["2026-07-11T04:41:48Z", "2026-07-11T06:18:56Z"],
        )


class QuietHoursTests(unittest.TestCase):
    def test_window_within_one_day(self):
        start, end = time(13, 0), time(15, 30)
        self.assertFalse(in_quiet_hours(time(12, 59), start, end))
        self.assertTrue(in_quiet_hours(time(13, 0), start, end), "start is inclusive")
        self.assertTrue(in_quiet_hours(time(14, 0), start, end))
        self.assertFalse(in_quiet_hours(time(15, 30), start, end), "end is exclusive")

    def test_window_crossing_midnight(self):
        start, end = time(22, 0), time(8, 0)
        self.assertTrue(in_quiet_hours(time(23, 30), start, end))
        self.assertTrue(in_quiet_hours(time(0, 0), start, end))
        self.assertTrue(in_quiet_hours(time(7, 59), start, end))
        self.assertFalse(in_quiet_hours(time(8, 0), start, end))
        self.assertFalse(in_quiet_hours(time(12, 0), start, end))
        self.assertFalse(in_quiet_hours(time(21, 59), start, end))


class ComposeTests(unittest.TestCase):
    def test_goal_style_line_and_subject(self):
        p = make_pass(
            visible=True,
            start_utc="2026-07-11T04:41:48Z",
            culmination_utc="2026-07-11T04:45:12Z",
            end_utc="2026-07-11T04:48:36Z",
            max_elevation_deg=77.9,
            start_compass="WSW",
            end_compass="ENE",
        )
        verdict = Verdict(p, "go", "cloud 5%, max elevation 78° — clear and high", 5)
        subject, body = compose([verdict], 47.61, -122.33, timezone.utc)
        self.assertIn("ISS tonight: 1 watchable pass", subject)
        self.assertIn("04:41", subject)
        self.assertIn("GO", subject)
        self.assertIn("04:41–04:48, max elevation 78°, WSW→ENE, cloud 5% — GO", body)
        self.assertIn("clear and high", body)
        self.assertIn("Location 47.61, -122.33", body)

    def test_unknown_cloud_rendered_honestly(self):
        verdict = Verdict(
            make_pass(visible=True, start_utc="2026-07-11T04:41:48Z"),
            "maybe",
            "no cloud forecast for this window yet",
            None,
        )
        _, body = compose([verdict], 47.61, -122.33, timezone.utc)
        self.assertIn("cloud unknown", body)

    def test_multiple_passes_counted_in_subject(self):
        verdicts = [
            verdict_at("2026-07-11T04:41:48Z", "go"),
            verdict_at("2026-07-11T06:18:56Z", "maybe"),
        ]
        subject, body = compose(verdicts, 47.61, -122.33, timezone.utc)
        self.assertIn("2 watchable passes", subject)
        self.assertEqual(body.count("— GO") + body.count("— MAYBE"), 2)

    def test_compose_requires_at_least_one(self):
        with self.assertRaises(ValueError):
            compose([], 47.61, -122.33, timezone.utc)


if __name__ == "__main__":
    unittest.main()
