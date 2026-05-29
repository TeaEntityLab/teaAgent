"""Sliding-window rate limiting for HTTP bearer tokens."""

from __future__ import annotations

import threading
import time


class TokenRateLimiter:
    """Per-key sliding-window limiter (typically keyed by token hash)."""

    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        if max_calls < 1:
            raise ValueError('max_calls must be >= 1')
        if window_seconds <= 0:
            raise ValueError('window_seconds must be positive')
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, list[float]] = {}

    def allow(self, key: str) -> tuple[bool, str]:
        """Return ``(True, '')`` or ``(False, reason)`` when quota exceeded."""
        now = time.monotonic()
        with self._lock:
            times = self._windows.setdefault(key, [])
            cutoff = now - self.window_seconds
            times[:] = [stamp for stamp in times if stamp >= cutoff]
            if len(times) >= self.max_calls:
                return (
                    False,
                    f'rate limit exceeded: {self.max_calls} requests per '
                    f'{self.window_seconds:g}s',
                )
            times.append(now)
        return True, ''
