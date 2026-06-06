"""ApprovalBackend abstract base class and built-in implementations.

Provides an extensible approval-decision boundary. The five built-in
backends mirror the five ``PermissionMode`` values. Enterprise integrators
can supply custom backends that implement ``ApprovalBackend.approve``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from teaagent.approval_manager import PermissionMode
from teaagent.errors import DenialReasonCode
from teaagent.read_only_gate import read_only_runtime_block_reason

# ---------------------------------------------------------------------------
# Decision value-objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalDecision:
    """Outcome of an ``ApprovalBackend.approve`` call."""

    approved: bool
    reason: str | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class ApprovalRequest:
    """Unified approval-request payload consumed by ``ApprovalBackend.approve``.

    Required fields:
        call_id, tool_name, arguments, reason, annotations, permission_mode

    Optional fields provide additional context that some backends need
    (e.g. plan-contract checks, handler source inspection in read-only mode).
    """

    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    annotations: dict[str, bool]
    permission_mode: PermissionMode
    # --- optional context ---
    plan_contract: Any = None
    read_only: bool | None = None
    description: str = ''
    handler: Any | None = None
    allow_all_destructive: bool = False
    full_access_acknowledged: bool = False


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ApprovalBackend(ABC):
    """Approval decision boundary for destructive tool calls.

    Subclasses implement the core allow/deny logic for a single
    permission mode.  The ``ApprovalManager`` calls ``approve`` once
    per tool call and then handles JIT prompting, store lookups,
    multi-sig quorum, and path containment on top of the backend's
    decision.
    """

    @abstractmethod
    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        """Return the mode-level decision for *request*.

        Returning ``ApprovalDecision(approved=True)`` means the tool
        is allowed at the mode level.  Returning ``approved=False``
        with ``reason_code='jit_required'`` signals that the caller
        should proceed to JIT / store / multi-sig approval.  Any other
        ``approved=False`` outcome is a hard denial.
        """
        ...


# ---------------------------------------------------------------------------
# Built-in backends (one per PermissionMode)
# ---------------------------------------------------------------------------


class ReadOnlyBackend(ApprovalBackend):
    """Denies all destructive tools; allows only verified read-only tools."""

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        destructive = request.annotations.get('destructive', False)
        read_only = request.read_only
        block_reason = read_only_runtime_block_reason(
            tool_name=request.tool_name,
            description=request.description,
            read_only=read_only,
            destructive=destructive,
            handler=request.handler,
        )
        if block_reason is not None:
            return ApprovalDecision(
                approved=False,
                reason=block_reason,
                reason_code=DenialReasonCode.READ_ONLY_MODE.value,
            )
        return ApprovalDecision(approved=True)


_WORKSPACE_WRITE_TOOL_NAMES: frozenset[str] = frozenset(
    {'workspace_write_file', 'workspace_apply_patch', 'workspace_edit_at_hash'}
)


class WorkspaceWriteBackend(ApprovalBackend):
    """Denies shell-mutate tools; allows file-write tools subject to plan contract."""

    _ALLOWED_DESTRUCTIVE: ClassVar[frozenset[str]] = _WORKSPACE_WRITE_TOOL_NAMES

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        if not request.annotations.get('destructive', False):
            return ApprovalDecision(approved=True)

        if request.tool_name in self._ALLOWED_DESTRUCTIVE:
            # --- plan-contract check (when both are present) ---
            if request.plan_contract is not None and request.arguments:
                file_path = (
                    request.arguments.get('path')
                    if isinstance(request.arguments, dict)
                    else None
                )
                if file_path and not request.plan_contract.allows_file_write(file_path):
                    return ApprovalDecision(
                        approved=False,
                        reason=(
                            f"Tool '{request.tool_name}' targeting '{file_path}' is "
                            f'not in approved plan file targets. '
                            f'Plan: {request.plan_contract.rel_path}'
                        ),
                        reason_code=DenialReasonCode.PLAN_CONTRACT_DENIED.value,
                    )
            return ApprovalDecision(approved=True)

        return ApprovalDecision(
            approved=False,
            reason=(
                f"Tool '{request.tool_name}' requires "
                'prompt/allow/danger-full-access permission mode.'
            ),
            reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE.value,
        )


class PromptBackend(ApprovalBackend):
    """Non-destructive tools pass automatically; destructive tools are routed
    to JIT prompting (sentinel ``reason_code='jit_required'``).

    The full-access gate (P0-TR-001) is enforced: setting
    ``allow_all_destructive`` in prompt mode does *not* bypass
    approval — it produces a hard denial.
    """

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        if not request.annotations.get('destructive', False):
            return ApprovalDecision(approved=True)

        if request.allow_all_destructive:
            return ApprovalDecision(
                approved=False,
                reason=(
                    f"Tool '{request.tool_name}' is destructive and "
                    "'allow_all_destructive' is enabled, but it only takes "
                    'effect in danger-full-access mode. '
                    'Use --permission-mode danger-full-access to proceed.'
                ),
                reason_code=DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED.value,
            )

        # Route to JIT / store / multi-sig via the caller.
        return ApprovalDecision(
            approved=False,
            reason_code='jit_required',
        )


class AllowBackend(ApprovalBackend):
    """Allows all destructive tools for the session."""

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=True)


class DangerFullAccessBackend(ApprovalBackend):
    """Allows all tools without restriction.

    Intended for trusted automation scenarios where a higher-level
    caller has already performed the full-access ceremony.
    """

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_BACKEND_BY_MODE: dict[PermissionMode, type[ApprovalBackend]] = {
    PermissionMode.READ_ONLY: ReadOnlyBackend,
    PermissionMode.WORKSPACE_WRITE: WorkspaceWriteBackend,
    PermissionMode.PROMPT: PromptBackend,
    PermissionMode.ALLOW: AllowBackend,
    PermissionMode.DANGER_FULL_ACCESS: DangerFullAccessBackend,
}


def backend_from_mode(mode: PermissionMode) -> ApprovalBackend:
    """Return the built-in ``ApprovalBackend`` for *mode*.

    Raises ``ValueError`` for unknown modes.
    """
    cls = _BACKEND_BY_MODE.get(mode)
    if cls is None:
        raise ValueError(f'Unknown permission mode: {mode!r}')
    return cls()


__all__ = [
    'AllowBackend',
    'ApprovalBackend',
    'ApprovalDecision',
    'ApprovalRequest',
    'DangerFullAccessBackend',
    'PromptBackend',
    'ReadOnlyBackend',
    'WorkspaceWriteBackend',
    'backend_from_mode',
]
