"""Run asyncio coroutines from synchronous call sites safely."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import Executor
from typing import Any, TypeVar

T = TypeVar('T')


def run_coroutine_sync(
    coro: Coroutine[Any, Any, T],
    *,
    executor: Executor | None = None,
    timeout_seconds: float | None = None,
) -> T:
    """Execute *coro* without replacing the current thread's event loop.

    When called from a thread that already has a running loop, the coroutine runs
    in a worker thread via ``asyncio.run`` (never ``asyncio.set_event_loop``).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if not loop.is_running():
        return asyncio.run(coro)

    if executor is None:
        raise RuntimeError(
            'run_coroutine_sync called from a running event loop without an executor'
        )

    future = executor.submit(asyncio.run, coro)
    if timeout_seconds is not None:
        return future.result(timeout=timeout_seconds)
    return future.result()
