"""Threading-based interval scheduler (ADR-0001; contract: docs/specs/operations.md).

Runs the cycle immediately on start (a fresh install gets data right away),
then every interval. A crashing cycle is logged and the loop keeps going —
this is an always-on service; one bad run must not end the schedule.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger("skywatch.scheduler")


class Scheduler:
    def __init__(
        self,
        run: Callable[[], object],
        interval_seconds: float,
        run_immediately: bool = True,
    ):
        self._run = run
        self._interval = interval_seconds
        self._run_immediately = run_immediately
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="skywatch-scheduler", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=join_timeout)

    def _loop(self) -> None:
        if self._run_immediately and not self._stop.is_set():
            self._safe_run()
        while not self._stop.wait(self._interval):
            self._safe_run()

    def _safe_run(self) -> None:
        try:
            self._run()
        except Exception:
            log.exception("scheduled cycle crashed; the schedule continues")
