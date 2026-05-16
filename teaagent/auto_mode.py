"""Auto mode: fully autonomous execution with safety budget."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class AutoModeConfig:
    """Safety budget for fully autonomous execution.

    When auto mode is enabled, the agent runs without any human-in-the-loop
    approval prompts.  All safety limits below act as hard stop conditions.
    """

    enabled: bool = False
    max_iterations: int = 50
    max_tool_calls: int = 100
    max_cost_cents: float = 500.0  # $5.00
    max_wall_clock_seconds: float = 600.0  # 10 minutes
    auto_commit: bool = False  # auto-commit on successful completion
    commit_message: str = 'auto: teaagent autonomous run'
    allowed_tools: Optional[frozenset[str]] = None  # None = all allowed
    denied_tools: frozenset[str] = frozenset(
        {
            'workspace_run_shell_mutate',
            'workspace_run_shell',
        }
    )


@dataclass
class AutoModeGuard:
    """Runtime guard that tracks resource consumption and enforces limits."""

    config: AutoModeConfig
    _iterations: int = 0
    _tool_calls: int = 0
    _cost_cents: float = 0.0
    _started_at: float = field(default_factory=time.monotonic)

    def record_iteration(self) -> None:
        self._iterations += 1
        self._check()

    def record_tool_call(self) -> None:
        self._tool_calls += 1
        self._check()

    def record_cost(self, cents: float) -> None:
        self._cost_cents += cents
        self._check()

    def is_tool_allowed(self, tool_name: str) -> bool:
        if self.config.allowed_tools is not None:
            return tool_name in self.config.allowed_tools
        return tool_name not in self.config.denied_tools

    def remaining_seconds(self) -> float:
        elapsed = time.monotonic() - self._started_at
        return max(0.0, self.config.max_wall_clock_seconds - elapsed)

    def _check(self) -> None:
        if self._iterations >= self.config.max_iterations:
            raise AutoModeLimitError(
                f'Auto mode: iteration limit reached ({self.config.max_iterations})'
            )
        if self._tool_calls >= self.config.max_tool_calls:
            raise AutoModeLimitError(
                f'Auto mode: tool-call limit reached ({self.config.max_tool_calls})'
            )
        if self._cost_cents >= self.config.max_cost_cents:
            raise AutoModeLimitError(
                f'Auto mode: cost limit reached (${self._cost_cents:.2f} / ${self.config.max_cost_cents / 100:.2f})'
            )
        elapsed = time.monotonic() - self._started_at
        if elapsed >= self.config.max_wall_clock_seconds:
            raise AutoModeLimitError(
                f'Auto mode: wall-clock limit reached ({elapsed:.0f}s / {self.config.max_wall_clock_seconds:.0f}s)'
            )

    def summary(self) -> dict[str, Any]:
        elapsed = time.monotonic() - self._started_at
        return {
            'auto_mode': True,
            'iterations': self._iterations,
            'tool_calls': self._tool_calls,
            'cost_cents': round(self._cost_cents, 2),
            'wall_clock_seconds': round(elapsed, 1),
            'limits': {
                'max_iterations': self.config.max_iterations,
                'max_tool_calls': self.config.max_tool_calls,
                'max_cost_cents': self.config.max_cost_cents,
                'max_wall_clock_seconds': self.config.max_wall_clock_seconds,
            },
        }


class AutoModeLimitError(RuntimeError):
    """Raised when an auto-mode safety limit is exceeded."""
