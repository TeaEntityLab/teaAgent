from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Optional

from teaagent.audit import AuditLogger

# Keys a progress provider may contribute to a heartbeat payload. Anything else
# (including ``tick`` and ``interval_seconds``) is ignored so a provider cannot
# corrupt the heartbeat's own counters.
PROGRESS_FIELDS = frozenset(
    {'tool', 'tool_in_flight', 'elapsed_seconds', 'cost_cents', 'checkpoint'}
)

# Returns the run's current progress snapshot, or None when nothing is known yet.
ProgressProvider = Callable[[], Optional[Mapping[str, object]]]


class Heartbeat:
    """Periodic liveness ticker that records progress for a long-running run.

    When a ``progress`` provider is given, each tick also carries the fields
    in ``PROGRESS_FIELDS`` that the provider returns. Without one, the payload
    holds only ``tick`` and ``interval_seconds``.
    """

    def __init__(
        self,
        audit: AuditLogger,
        run_id: str,
        *,
        interval_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        liveness_root: Path | None = None,
        progress: ProgressProvider | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive')
        self.audit = audit
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self._sleep = sleep
        self._liveness_root = liveness_root
        self._progress = progress
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.tick_count = 0

    def __enter__(self) -> 'Heartbeat':
        self.start()
        return self

    def __exit__(self, _exc_type: object, _exc_val: object, _exc_tb: object) -> None:
        self.stop()

    def tick(self) -> None:
        self.tick_count += 1
        self.audit.record(
            'heartbeat',
            self.run_id,
            **self._payload(),
        )
        if self._liveness_root is not None:
            from teaagent.ergonomics.run_liveness import touch_liveness

            touch_liveness(
                self._liveness_root,
                self.run_id,
                tick=self.tick_count,
                interval_seconds=self.interval_seconds,
            )

    def _payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'tick': self.tick_count,
            'interval_seconds': self.interval_seconds,
        }
        if self._progress is None:
            return payload
        try:
            snapshot = self._progress()
        except Exception:
            # A broken progress source must never stop the liveness signal.
            payload['progress_unavailable'] = True
            return payload
        if snapshot:
            payload.update({k: v for k, v in snapshot.items() if k in PROGRESS_FIELDS})
        return payload

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name=f'heartbeat-{self.run_id}', daemon=True
        )
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
