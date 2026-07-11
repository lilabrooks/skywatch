import unittest
from datetime import datetime, timezone

from skywatch import db, page
from skywatch.cycle import run_cycle
from tests.support import make_config
from tests.test_cycle import clear_fetch, fake_fetch

FIXED_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.config = make_config()

    def render(self):
        return page.render(self.config, self.conn, FIXED_NOW, timezone.utc)

    def test_empty_database_renders_clean_empty_state(self):
        body = self.render()
        self.assertIn("No data yet", body)
        self.assertIn("make cycle", body)
        self.assertIn("47.61, -122.33", body)
        self.assertNotIn("<table", body)

    def test_populated_page_lists_upcoming_verdicts_with_reasons(self):
        run_cycle(self.conn, self.config, clear_fetch(), lambda: FIXED_NOW)
        body = self.render()
        self.assertIn("Last cycle 2026-07-10 12:00 UTC", body)
        self.assertIn("passes ok: 8 passes", body)
        self.assertIn("badge go", body)
        self.assertIn("clear and high", body)
        self.assertIn("Sat 2026-07-11 04:41–04:48", body)
        self.assertIn("78°", body)
        self.assertIn("WSW→ENE", body)
        self.assertIn("not visible", body, "skips appear with their reasons")

    def test_cycle_without_upcoming_passes_says_so(self):
        run_cycle(
            self.conn,
            self.config,
            fake_fetch(passes=[], forecast="fixture"),
            lambda: FIXED_NOW,
        )
        body = self.render()
        self.assertIn("No upcoming passes", body)
        self.assertIn("Last cycle", body)

    def test_dynamic_content_is_escaped(self):
        cycle_id = db.start_cycle(self.conn, "2026-07-10T11:00:00Z")
        db.finish_cycle(
            self.conn,
            cycle_id,
            "2026-07-10T11:00:05Z",
            'error: <script>alert("x")</script>',
            "ok: 48 hours",
        )
        body = self.render()
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_stylesheet_exposes_verdict_badges(self):
        self.assertIn(".badge.go", page.STYLESHEET)
        self.assertIn(".badge.maybe", page.STYLESHEET)


if __name__ == "__main__":
    unittest.main()
