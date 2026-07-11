import threading
import time
import unittest

from skywatch.scheduler import Scheduler


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class SchedulerTests(unittest.TestCase):
    def test_runs_immediately_then_on_interval(self):
        calls = []
        scheduler = Scheduler(lambda: calls.append(time.monotonic()), interval_seconds=0.05)
        scheduler.start()
        try:
            self.assertTrue(wait_until(lambda: len(calls) >= 3), f"only {len(calls)} runs")
        finally:
            scheduler.stop()

    def test_stop_halts_promptly_even_mid_wait(self):
        calls = []
        scheduler = Scheduler(lambda: calls.append(1), interval_seconds=60)
        scheduler.start()
        self.assertTrue(wait_until(lambda: len(calls) == 1))
        started = time.monotonic()
        scheduler.stop()
        self.assertLess(time.monotonic() - started, 5, "stop must not wait out the interval")
        count = len(calls)
        time.sleep(0.05)
        self.assertEqual(len(calls), count, "no runs after stop")

    def test_crashing_run_does_not_end_the_schedule(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")

        scheduler = Scheduler(flaky, interval_seconds=0.05)
        scheduler.start()
        try:
            self.assertTrue(
                wait_until(lambda: len(calls) >= 3),
                "the loop must survive a crashing cycle",
            )
        finally:
            scheduler.stop()

    def test_run_immediately_false_waits_for_the_interval(self):
        calls = []
        ran = threading.Event()

        def record():
            calls.append(1)
            ran.set()

        scheduler = Scheduler(record, interval_seconds=0.2, run_immediately=False)
        scheduler.start()
        try:
            self.assertFalse(ran.wait(0.05), "must not run before the first interval")
            self.assertTrue(ran.wait(2.0), "must run after the interval")
        finally:
            scheduler.stop()


if __name__ == "__main__":
    unittest.main()
