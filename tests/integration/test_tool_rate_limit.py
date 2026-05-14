"""IT-3: ToolRegistry rate limiter blocks calls that exceed the quota.

Verifies the sliding-window enforcement, concurrency safety, and that the
``call_count`` helper is accurate.
"""

from __future__ import annotations

import threading
import time

import pytest

from teaagent.errors import ToolExecutionError
from teaagent.tools import ToolAnnotations, ToolRateLimit, ToolRegistry


def _make_registry_with_rate_limit(max_calls: int, window: float) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='limited',
        description='rate-limited tool',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {'ok': {'type': 'boolean'}}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {'ok': True},
        rate_limit=ToolRateLimit(max_calls=max_calls, window_seconds=window),
    )
    return registry


def test_calls_within_quota_succeed():
    registry = _make_registry_with_rate_limit(max_calls=3, window=60.0)
    for _ in range(3):
        result = registry.execute('limited', {})
        assert result == {'ok': True}


def test_call_exceeding_quota_raises():
    registry = _make_registry_with_rate_limit(max_calls=2, window=60.0)
    registry.execute('limited', {})
    registry.execute('limited', {})
    with pytest.raises(ToolExecutionError, match='rate limit exceeded'):
        registry.execute('limited', {})


def test_call_count_helper():
    registry = _make_registry_with_rate_limit(max_calls=10, window=60.0)
    assert registry.call_count('limited') == 0
    registry.execute('limited', {})
    registry.execute('limited', {})
    assert registry.call_count('limited') == 2


def test_window_expiry_resets_quota():
    registry = _make_registry_with_rate_limit(max_calls=1, window=0.1)
    registry.execute('limited', {})
    with pytest.raises(ToolExecutionError):
        registry.execute('limited', {})
    time.sleep(0.15)  # wait for window to expire
    # Should succeed again after window slides
    result = registry.execute('limited', {})
    assert result == {'ok': True}


def test_no_rate_limit_call_count_returns_zero():
    registry = ToolRegistry()
    registry.register(
        name='unlimited',
        description='no rate limit',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {},
    )
    assert registry.call_count('unlimited') == 0


def test_concurrent_calls_respect_quota():
    registry = _make_registry_with_rate_limit(max_calls=5, window=60.0)
    errors: list[Exception] = []
    successes: list[bool] = []
    lock = threading.Lock()

    def call_tool():
        try:
            registry.execute('limited', {})
            with lock:
                successes.append(True)
        except ToolExecutionError as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=call_tool) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 5, f'expected exactly 5 successes, got {len(successes)}'
    assert len(errors) == 5, f'expected exactly 5 errors, got {len(errors)}'
