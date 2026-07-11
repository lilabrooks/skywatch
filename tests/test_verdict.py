import unittest

from skywatch.verdict import GO, MAYBE, SKIP, hours_touched, judge, judge_pass
from tests.support import make_config, make_pass


def visible_pass(**overrides):
    values = {
        "visible": True,
        "start_utc": "2026-07-11T04:41:48Z",
        "culmination_utc": "2026-07-11T04:45:12Z",
        "end_utc": "2026-07-11T04:48:36Z",
        "max_elevation_deg": 77.9,
    }
    values.update(overrides)
    return make_pass(**values)


CLEAR = {"2026-07-11T04:00:00Z": 10}
CONFIG = make_config()


class JudgePassTests(unittest.TestCase):
    def test_invisible_pass_skips_regardless_of_weather(self):
        verdict = judge_pass(make_pass(visible=False), CLEAR, CONFIG)
        self.assertEqual(verdict.verdict, SKIP)
        self.assertIn("not visible", verdict.reason)

    def test_low_pass_skips_naming_threshold(self):
        verdict = judge_pass(visible_pass(max_elevation_deg=15.3), CLEAR, CONFIG)
        self.assertEqual(verdict.verdict, SKIP)
        self.assertIn("too low", verdict.reason)
        self.assertIn("25°", verdict.reason)

    def test_clear_high_pass_goes(self):
        verdict = judge_pass(visible_pass(), CLEAR, CONFIG)
        self.assertEqual(verdict.verdict, GO)
        self.assertEqual(verdict.cloud_cover_pct, 10)
        self.assertIn("cloud 10%", verdict.reason)
        self.assertIn("78°", verdict.reason)

    def test_middling_cloud_is_maybe(self):
        verdict = judge_pass(visible_pass(), {"2026-07-11T04:00:00Z": 53}, CONFIG)
        self.assertEqual(verdict.verdict, MAYBE)
        self.assertIn("cloud 53%", verdict.reason)

    def test_overcast_skips(self):
        verdict = judge_pass(visible_pass(), {"2026-07-11T04:00:00Z": 100}, CONFIG)
        self.assertEqual(verdict.verdict, SKIP)
        self.assertIn("overcast", verdict.reason)

    def test_missing_forecast_is_maybe_with_reason(self):
        verdict = judge_pass(visible_pass(), {}, CONFIG)
        self.assertEqual(verdict.verdict, MAYBE)
        self.assertIsNone(verdict.cloud_cover_pct)
        self.assertIn("no cloud forecast", verdict.reason)

    def test_straddling_pass_uses_worst_hour(self):
        straddler = visible_pass(
            start_utc="2026-07-11T20:58:00Z",
            culmination_utc="2026-07-11T21:01:00Z",
            end_utc="2026-07-11T21:04:00Z",
        )
        clouds = {"2026-07-11T20:00:00Z": 10, "2026-07-11T21:00:00Z": 95}
        verdict = judge_pass(straddler, clouds, CONFIG)
        self.assertEqual(verdict.verdict, SKIP)
        self.assertEqual(verdict.cloud_cover_pct, 95)

    def test_thresholds_come_from_config(self):
        lenient = make_config(cloud_go_max=60, cloud_maybe_max=90)
        verdict = judge_pass(visible_pass(), {"2026-07-11T04:00:00Z": 53}, lenient)
        self.assertEqual(verdict.verdict, GO)

    def test_min_elevation_comes_from_config(self):
        strict = make_config(min_elevation_deg=80.0)
        verdict = judge_pass(visible_pass(), CLEAR, strict)
        self.assertEqual(verdict.verdict, SKIP)


class HoursTouchedTests(unittest.TestCase):
    def test_pass_within_one_hour(self):
        self.assertEqual(
            hours_touched("2026-07-11T04:41:48Z", "2026-07-11T04:48:36Z"),
            ["2026-07-11T04:00:00Z"],
        )

    def test_pass_straddling_hours(self):
        self.assertEqual(
            hours_touched("2026-07-11T20:58:00Z", "2026-07-11T21:04:00Z"),
            ["2026-07-11T20:00:00Z", "2026-07-11T21:00:00Z"],
        )

    def test_pass_starting_on_the_hour(self):
        self.assertEqual(
            hours_touched("2026-07-11T21:00:00Z", "2026-07-11T21:06:00Z"),
            ["2026-07-11T21:00:00Z"],
        )


class JudgeListTests(unittest.TestCase):
    def test_one_verdict_per_pass_in_order(self):
        passes = [make_pass(visible=False), visible_pass()]
        verdicts = judge(passes, CLEAR, CONFIG)
        self.assertEqual([v.verdict for v in verdicts], [SKIP, GO])
        self.assertEqual([v.pass_ for v in verdicts], passes)


if __name__ == "__main__":
    unittest.main()
