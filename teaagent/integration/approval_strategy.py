"""Approval strategy boundary for CLI, TUI, tests, and remote flows (WS5-003)."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from teaagent.policy import ApprovalPolicy
from teaagent.runner._types import ApprovalHandler, ApprovalRequest


@runtime_checkable
class ApprovalStrategy(Protocol):
    """Decision boundary for destructive tool approval."""

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any],
        reason_code: Optional[str] = None,
    ) -> None:
        """Raise when the tool call must not proceed without approval."""

    def to_handler(self) -> ApprovalHandler:
        """Adapt to the runner ``ApprovalHandler`` callback shape."""


class PolicyApprovalStrategy:
    """Strategy backed by the unified ``ApprovalPolicy`` / ``ApprovalManager``."""

    def __init__(self, policy: ApprovalPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> ApprovalPolicy:
        return self._policy

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any],
        reason_code: Optional[str] = None,
    ) -> None:
        self._policy.assert_allowed(
            tool_name=tool_name,
            call_id=call_id,
            destructive=destructive,
            arguments=arguments,
        )

    def to_handler(self) -> ApprovalHandler:
        def _handler(request: ApprovalRequest) -> bool:
            try:
                self._policy.assert_allowed(
                    tool_name=request.tool_name,
                    call_id=request.call_id,
                    destructive=True,
                    arguments=request.arguments,
                )
            except Exception:
                return False
            return True

        return _handler


class CallbackApprovalStrategy:
    """Strategy that delegates interactive approval to a callback."""

    def __init__(self, handler: ApprovalHandler) -> None:
        self._handler = handler

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any],
        reason_code: Optional[str] = None,
    ) -> None:
        if not destructive:
            return
        approved = self._handler(
            ApprovalRequest(
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                reason=reason_code or 'destructive tool requires approval',
                annotations={'destructive': True},
            )
        )
        if not approved:
            from teaagent.errors import ToolPermissionError

            raise ToolPermissionError('approval denied')

    def to_handler(self) -> ApprovalHandler:
        return self._handler


def approval_strategy_from_policy(policy: ApprovalPolicy) -> PolicyApprovalStrategy:
    return PolicyApprovalStrategy(policy)


def approval_handler_from_strategy(strategy: ApprovalStrategy) -> ApprovalHandler:
    return strategy.to_handler()
