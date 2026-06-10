"""Circuit breaker pattern for resilient Redis operations."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = 'closed'  # Normal operation
    OPEN = 'open'  # Circuit is open, blocking calls
    HALF_OPEN = 'half_open'  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Number of failures before opening
    timeout_seconds: int = 60  # How long to stay open before trying again
    success_threshold: int = 2  # Number of successes to close circuit in half-open


class CircuitBreaker:
    """Circuit breaker for resilient service calls.

    Prevents cascading failures by blocking calls to a failing service
    after a threshold of failures is reached.
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Call function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function call

        Raises:
            Exception: If circuit is open or function call fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time > self.config.timeout_seconds

    def _on_success(self) -> None:
        """Handle successful call."""
        self.successes += 1
        self.last_success_time = time.time()

        if (
            self.state == CircuitState.HALF_OPEN
            and self.successes >= self.config.success_threshold
        ):
            self.state = CircuitState.CLOSED
            self.failures = 0
            self.successes = 0
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.successes = 0
            logger.warning(f"Circuit breaker '{self.name}' opened from HALF_OPEN state")
        elif self.failures >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker '{self.name}' opened after {self.failures} failures"
            )

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = None
        self.last_success_time = None
        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failures': self.failures,
            'successes': self.successes,
            'last_failure_time': self.last_failure_time,
            'last_success_time': self.last_success_time,
        }
