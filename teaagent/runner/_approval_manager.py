"""Approval workflow management for AgentRunner."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.audit import AuditLogger
from teaagent.policy import ApprovalPolicy, JITApprovalState, PermissionMode

from ._types import ApprovalHandler, ApprovalRequest


class RunnerApprovalCoordinator:
    """Handles approval workflow for tool calls.

    Manages the approval process including:
    - Checking if approval can be requested
    - Creating approval requests
    - Recording audit events
    - Handling approval handler callbacks
    """

    def __init__(
        self,
        *,
        approval_policy: ApprovalPolicy,
        approval_handler: Optional[ApprovalHandler] = None,
        jit_state: Optional[JITApprovalState] = None,
    ) -> None:
        self.approval_policy = approval_policy
        self.approval_handler = approval_handler
        self.jit_state = jit_state or JITApprovalState()

    def can_request_approval(self, destructive: bool) -> bool:
        """Check if approval can be requested for a tool call."""
        return (
            destructive
            and self.approval_policy.permission_mode == PermissionMode.PROMPT
        )

    def create_approval_request(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
        annotations: dict[str, Any],
        run_id: str,
    ) -> ApprovalRequest:
        """Create an approval request for a tool call."""
        secret = None
        if self.approval_policy and self.approval_policy.approval_store:
            secret = self.approval_policy.approval_store._get_workspace_secret()

        return ApprovalRequest(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            annotations=annotations,
            run_id=run_id,
            workspace_secret=secret,
        )

    def handle_approval_request(
        self,
        approval_request: ApprovalRequest,
        audit: AuditLogger,
        run_id: str,
        checkpoint_store: Any = None,
        context: Optional[dict[str, Any]] = None,
        cost_cents: float = 0.0,
        reason_code: Optional[str] = None,
    ) -> bool:
        """Handle an approval request through the approval handler.

        Returns True if approved, False if denied.
        """
        pending_payload = approval_request.to_dict()
        pending_payload.pop('run_id', None)
        if reason_code is not None:
            pending_payload['reason_code'] = reason_code
        audit.record(
            'tool_call_pending_approval',
            run_id,
            **pending_payload,
        )

        if self.approval_handler is None:
            audit.record(
                'run_paused',
                run_id,
                status='pending_approval',
                approval=approval_request.to_dict(),
                cost_cents=cost_cents,
            )
            if checkpoint_store is not None and context is not None:
                checkpoint_store.save(run_id, context)
            return False

        if self.approval_handler(approval_request):
            audit.record(
                'tool_call_approved',
                run_id,
                call_id=approval_request.call_id,
                tool_name=approval_request.tool_name,
                authority_type='jit_prompt',
                approved_by='user',
            )
            return True
        else:
            denied_payload: dict[str, Any] = {
                'call_id': approval_request.call_id,
                'tool_name': approval_request.tool_name,
            }
            if reason_code is not None:
                denied_payload['reason_code'] = reason_code
            audit.record(
                'tool_call_denied',
                run_id,
                **denied_payload,
            )
            return False

    def record_blocked(
        self,
        approval_request: ApprovalRequest,
        audit: AuditLogger,
        run_id: str,
        reason_code: Optional[str] = None,
    ) -> None:
        """Record a blocked tool call in the audit log."""
        blocked_payload = approval_request.to_dict()
        blocked_payload.pop('run_id', None)
        if reason_code is not None:
            blocked_payload['reason_code'] = reason_code
        blocked_payload['authority_type'] = reason_code or 'policy_blocked'
        audit.record(
            'tool_call_blocked',
            run_id,
            **blocked_payload,
        )
