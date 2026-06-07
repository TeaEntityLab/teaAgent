"""In-process operation metrics for CLI and diagnostics."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperationMetrics:
    """Thread-safe counters and histogram samples for harness operations."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    histograms: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def increment(self, name: str, *, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self.histograms[name].append(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                'counters': dict(self.counters),
                'histograms': {
                    key: {
                        'count': len(values),
                        'sum': sum(values),
                        'max': max(values) if values else 0.0,
                    }
                    for key, values in self.histograms.items()
                },
            }


_GLOBAL_METRICS = OperationMetrics()


def get_operation_metrics() -> OperationMetrics:
    return _GLOBAL_METRICS
