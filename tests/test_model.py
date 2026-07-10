import unittest
from datetime import datetime, timezone

from skywatch.model import compass_point, parse_utc, to_utc_z


class TimeHelperTests(unittest.TestCase):
    def test_to_utc_z_second_precision(self):
        moment = datetime(2026, 7, 11, 3, 6, 46, 992415, tzinfo=timezone.utc)
        self.assertEqual(to_utc_z(moment), "2026-07-11T03:06:46Z")

    def test_to_utc_z_rejects_naive(self):
        with self.assertRaises(ValueError):
            to_utc_z(datetime(2026, 7, 11, 3, 0, 0))

    def test_parse_utc_variants(self):
        expected = datetime(2026, 7, 11, 3, 6, 46, tzinfo=timezone.utc)
        for text in (
            "2026-07-11T03:06:46Z",
            "2026-07-11T03:06:46+00:00",
            "2026-07-11 03:06:46+00:00",
            "2026-07-11T03:06:46",  # naive treated as UTC
        ):
            self.assertEqual(parse_utc(text).replace(microsecond=0), expected, text)

    def test_parse_utc_converts_offsets(self):
        self.assertEqual(
            parse_utc("2026-07-11T05:06:46+02:00"),
            datetime(2026, 7, 11, 3, 6, 46, tzinfo=timezone.utc),
        )

    def test_roundtrip_terrestre_style_stamp(self):
        self.assertEqual(
            to_utc_z(parse_utc("2026-07-11 03:06:46.992415+00:00")),
            "2026-07-11T03:06:46Z",
        )


class CompassTests(unittest.TestCase):
    def test_cardinal_and_intercardinal_points(self):
        cases = {
            0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S",
            225: "SW", 247.5: "WSW", 270: "W", 315: "NW", 359: "N",
        }
        for degrees, name in cases.items():
            self.assertEqual(compass_point(degrees), name, degrees)

    def test_wraps_outside_0_360(self):
        self.assertEqual(compass_point(360), "N")
        self.assertEqual(compass_point(-22.5), "NNW")
        self.assertEqual(compass_point(742.5), "NNE")  # 742.5 % 360 = 22.5


if __name__ == "__main__":
    unittest.main()
