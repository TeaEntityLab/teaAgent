from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from teaagent.llm._types import LLMHTTPError


@dataclass(frozen=True)
class LLMRetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    retry_on_status: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    def delay(self, attempt: int) -> float:
        delay = self.base_delay_seconds * (2**attempt)
        max_jitter_ms = int(delay * 500)  # Convert to milliseconds
        jitter = secrets.randbelow(max_jitter_ms) / 1000
        return min(delay + jitter, self.max_delay_seconds)


DEFAULT_RETRY_CONFIG = LLMRetryConfig()


def _call_with_retry(
    provider: str,
    transport_fn: Callable[[], dict[str, Any]],
    retry_config: LLMRetryConfig,
) -> dict[str, Any]:
    last_exc: Optional[LLMHTTPError] = None
    for attempt in range(retry_config.max_retries + 1):
        try:
            return transport_fn()
        except LLMHTTPError as exc:
            last_exc = exc
            if attempt >= retry_config.max_retries:
                raise
            is_transient = exc.status_code in retry_config.retry_on_status
            is_network = exc.status_code == 0
            if is_transient or is_network:
                time.sleep(retry_config.delay(attempt))
                continue
            raise
    if last_exc is None:
        raise RuntimeError('No exception captured during retries')
    raise last_exc
