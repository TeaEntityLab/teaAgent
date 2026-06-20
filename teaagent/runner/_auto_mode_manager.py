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

    def get_auto_approve_policy(
        self,
        *,
        parent_policy: ApprovalPolicy,
        tool_name: str,
        arguments: dict[str, Any],
        destructive: bool,
    ) -> Optional[tuple[ApprovalPolicy, str]]:
        """Get a payload-scoped approval policy for an auto-mode tool call.

        Returns a scoped ``ApprovalPolicy`` preapproved for the specific
        ``(tool_name, arguments)`` digest, or ``None`` when auto mode is
        disabled or the call is non-destructive.  The caller is responsible for
        emitting the ``tool_call_approved`` audit event.
        """
        if self.auto_mode_guard is None:
            return None
        if not destructive:
            return None
        from teaagent.policy import compute_scoped_payload_digest

        digest = compute_scoped_payload_digest(tool_name, arguments)
        scoped = ApprovalPolicy(
            permission_mode=parent_policy.permission_mode,
            approval_store=parent_policy.approval_store,
            approval_origin_run_id=parent_policy.approval_origin_run_id,
            preapproved_payload_digests=frozenset({digest}),
            enable_jit_prompt=parent_policy.enable_jit_prompt,
            multi_sig_config=parent_policy.multi_sig_config,
            agent_id=parent_policy.agent_id,
            workspace_root=parent_policy.workspace_root,
            tenant_id=parent_policy.tenant_id,
        )
        return scoped, digest

    def summary(self) -> dict[str, Any]:
        """Get a summary of auto mode activity."""
        if self.auto_mode_guard is None:
            return {}
        return self.auto_mode_guard.summary()
