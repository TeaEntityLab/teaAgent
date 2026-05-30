"""Auto mode management for AgentRunner."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.auto_mode import AutoModeConfig, AutoModeGuard
from teaagent.errors import ToolPermissionError
from teaagent.policy import ApprovalPolicy


class AutoModeManager:
    """Handles auto mode logic for tool calls.

    Manages auto mode functionality including:
    - Tracking iterations and tool calls
    - Validating tool permissions in auto mode
    - Modifying approval policy for auto-approved tools
    - Providing auto mode summaries
    """

    def __init__(self, *, auto_mode_config: Optional[AutoModeConfig] = None) -> None:
        self.auto_mode_guard: Optional[AutoModeGuard] = None
        if auto_mode_config is not None and auto_mode_config.enabled:
            self.auto_mode_guard = AutoModeGuard(config=auto_mode_config)

    def is_enabled(self) -> bool:
        """Check if auto mode is enabled."""
        return self.auto_mode_guard is not None

    def record_iteration(self) -> None:
        """Record an iteration in auto mode."""
        if self.auto_mode_guard is not None:
            self.auto_mode_guard.record_iteration()

    def record_tool_call(self) -> None:
        """Record a tool call in auto mode."""
        if self.auto_mode_guard is not None:
            self.auto_mode_guard.record_tool_call()

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed in auto mode."""
        if self.auto_mode_guard is None:
            return True
        return self.auto_mode_guard.is_tool_allowed(tool_name)

    def validate_tool_allowed(self, tool_name: str) -> None:
        """Validate that a tool is allowed in auto mode, raise error if not."""
        if self.auto_mode_guard is not None and not self.is_tool_allowed(tool_name):
            raise ToolPermissionError(f"Auto mode: tool '{tool_name}' is not allowed")

    def get_auto_approve_policy(self) -> Optional[ApprovalPolicy]:
        """Get the approval policy modified for auto mode.

        In auto mode, allowed tools are auto-approved by setting allow_all_destructive=True.
        """
        if self.auto_mode_guard is None:
            return None
        return ApprovalPolicy(allow_all_destructive=True)

    def summary(self) -> dict[str, Any]:
        """Get a summary of auto mode activity."""
        if self.auto_mode_guard is None:
            return {}
        return self.auto_mode_guard.summary()
