"""Preset and scoped-approval store adapter used by the approval manager.

Moved unchanged from ``teaagent.approval.manager`` (A-P1-6 split, ADR-0044).
``teaagent.approval.manager`` re-exports ``ApprovalStoreManager``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore


class ApprovalStoreManager:
    """Manages approval store presets and scoped approvals (ADR-002)."""

    def __init__(
        self,
        approval_store: ApprovalPresetStore | None = None,
        approval_origin_run_id: str | None = None,
    ) -> None:
        self.approval_store = approval_store
        self.approval_origin_run_id = approval_origin_run_id

    def check_preset(
        self,
        *,
        tool_name: str,
        permission_mode: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        if not self.approval_store:
            return 'prompt'
        result = self.approval_store.check(
            tool_name,
            permission_mode=permission_mode,
            arguments=arguments,
        )
        decision = result.get('decision', 'prompt')
        if decision in ('allow', 'deny'):
            return decision
        return 'prompt'

    def check_scoped(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        if not self.approval_store or not self.approval_origin_run_id:
            return False
        return self.approval_store.try_consume_scoped_approval(
            run_id=self.approval_origin_run_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        )

    # NOTE: handle_preapproved (call-id preapproval) was removed (G-P2-2).
    # Call ids are predictable, so call-id-scoped preapproval was weaker
    # authority than a payload digest; use handle_payload_digest_preapproved.

    def handle_payload_digest_preapproved(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        preapproved_payload_digests: frozenset[str],
    ) -> bool:
        from teaagent.policy import compute_scoped_payload_digest

        if not self.approval_store or not self.approval_origin_run_id:
            return False
        digest = compute_scoped_payload_digest(tool_name, arguments)
        if digest not in preapproved_payload_digests:
            return False
        if (
            self.approval_store.check_scoped_approval(
                run_id=self.approval_origin_run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
            )
            is None
        ):
            self.approval_store.add_scoped_approval(
                run_id=self.approval_origin_run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
            )
        return self.approval_store.try_consume_scoped_approval(
            run_id=self.approval_origin_run_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        )
