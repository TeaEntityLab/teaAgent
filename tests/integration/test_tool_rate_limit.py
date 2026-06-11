"""IT-3: ToolRegistry rate limiter blocks calls that exceed the quota.

Verifies the sliding-window enforcement, concurrency safety, and that the
``call_count`` helper is accurate.

The sliding-window rate limiter tracks tool calls within a time window and
blocks calls that exceed the maximum allowed calls. After the window expires,
the quota resets and calls are allowed again. This prevents tool abuse and
ensures fair resource allocation.
"""

from __future__ import annotations

import threading
import time

import pytest

from teaagent.types import (
    ToolAnnotations,
    ToolExecutionError,
    ToolRateLimit,
    ToolRegistry,
)

# Rate limit test constants
_RATE_LIMIT_MAX_CALLS_STANDARD = 3  # Standard max calls for quota tests
_RATE_LIMIT_MAX_CALLS_LOW = 2  # Low max calls for quota exceed test
_RATE_LIMIT_MAX_CALLS_HIGH = 10  # High max calls for call count test
_RATE_LIMIT_MAX_CALLS_SINGLE = 1  # Single call for window expiry test
_RATE_LIMIT_MAX_CALLS_CONCURRENT = 5  # Max calls for concurrent test
_RATE_LIMIT_WINDOW_LONG = 60.0  # Long window (seconds) for standard tests
_RATE_LIMIT_WINDOW_SHORT = 0.1  # Short window (seconds) for expiry test
_RATE_LIMIT_SLEEP_TIME = 0.15  # Sleep time (seconds) to wait for window expiry
_RATE_LIMIT_CONCURRENT_THREADS = 10  # Number of concurrent threads for test
_RATE_LIMIT_EXPECTED_SUCCESSES = 5  # Expected successful calls in concurrent test
_RATE_LIMIT_EXPECTED_ERRORS = 5  # Expected errors in concurrent test


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
    registry = _make_registry_with_rate_limit(
        max_calls=_RATE_LIMIT_MAX_CALLS_STANDARD, window=_RATE_LIMIT_WINDOW_LONG
    )
    for _ in range(_RATE_LIMIT_MAX_CALLS_STANDARD):
        result = registry.execute('limited', {})
        assert result == {'ok': True}


def test_call_exceeding_quota_raises():
    registry = _make_registry_with_rate_limit(
        max_calls=_RATE_LIMIT_MAX_CALLS_LOW, window=_RATE_LIMIT_WINDOW_LONG
    )
    registry.execute('limited', {})
    registry.execute('limited', {})
    with pytest.raises(ToolExecutionError, match='rate limit exceeded'):
        registry.execute('limited', {})


def test_call_count_helper():
    registry = _make_registry_with_rate_limit(
        max_calls=_RATE_LIMIT_MAX_CALLS_HIGH, window=_RATE_LIMIT_WINDOW_LONG
    )
    assert registry.call_count('limited') == 0
    registry.execute('limited', {})
    registry.execute('limited', {})
    assert registry.call_count('limited') == 2


def test_window_expiry_resets_quota():
    registry = _make_registry_with_rate_limit(
        max_calls=_RATE_LIMIT_MAX_CALLS_SINGLE, window=_RATE_LIMIT_WINDOW_SHORT
    )
    registry.execute('limited', {})
    with pytest.raises(ToolExecutionError):
        registry.execute('limited', {})
    time.sleep(_RATE_LIMIT_SLEEP_TIME)  # wait for window to expire
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
    registry = _make_registry_with_rate_limit(
        max_calls=_RATE_LIMIT_MAX_CALLS_CONCURRENT, window=_RATE_LIMIT_WINDOW_LONG
    )
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

    threads = [
        threading.Thread(target=call_tool)
        for _ in range(_RATE_LIMIT_CONCURRENT_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == _RATE_LIMIT_EXPECTED_SUCCESSES, (
        f'expected exactly {_RATE_LIMIT_EXPECTED_SUCCESSES} successes, got {len(successes)}'
    )
    assert len(errors) == _RATE_LIMIT_EXPECTED_ERRORS, (
        f'expected exactly {_RATE_LIMIT_EXPECTED_ERRORS} errors, got {len(errors)}'
    )
