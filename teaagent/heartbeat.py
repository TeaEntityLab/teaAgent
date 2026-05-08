from __future__ import annotations

import threading
import time
from typing import Optional

from teaagent.audit import AuditLogger


class Heartbeat:
    """Periodic 'heartbeat' audit events for long-running runs."""

    def __init__(
        self,
        audit: AuditLogger,
        run_id: str,
        *,
        interval_seconds: float,
        sleep=time.sleep,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.audit = audit
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self._sleep = sleep
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.tick_count = 0

    def __enter__(self) -> "Heartbeat":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def tick(self) -> None:
        self.tick_count += 1
        self.audit.record(
            "heartbeat",
            self.run_id,
            tick=self.tick_count,
            interval_seconds=self.interval_seconds,
        )

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name=f"heartbeat-{self.run_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds * 4)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.interval_seconds):
                return
            self.tick()
