"""Shared agent run setup contract (WS5-001)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.policy import ApprovalPolicy, MultiSigQuorumConfig, PermissionMode
from teaagent.run_store import RunStore
from teaagent.tools import ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


@dataclass(frozen=True)
class RunSetupRequest:
    """Portable run bootstrap inputs for CLI, TUI, chat, and tests."""

    root: Path
    permission_mode: PermissionMode = PermissionMode.PROMPT
    allow_destructive: bool = False
    max_iterations: int = 10
    max_tool_calls: int = 10
    max_estimated_cost_cents: int | None = 500
    approved_call_ids: frozenset[str] = frozenset()
    use_approval_store: bool = True
    run_id: str | None = None
    resumed_from: str | None = None
    load_plugins: bool = True
    hook_registry: Any = None
    require_plan: bool = False
    skip_plan_check: bool = False
    registry: ToolRegistry | None = None


@dataclass
class PreparedAgentRun:
    """Objects produced by the shared run setup path."""

    root: Path
    run_store: RunStore
    registry: ToolRegistry
    audit: AuditLogger
    budget: RunBudget
    approval_policy: ApprovalPolicy
    run_id: str
    plugin_load_failed: list[str]


def build_run_budget(
    *,
    max_iterations: int = 10,
    max_tool_calls: int = 10,
    max_estimated_cost_cents: int | None = 500,
) -> RunBudget:
    return RunBudget(
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
        max_estimated_cost_cents=max_estimated_cost_cents,
    )


def build_approval_policy(
    request: RunSetupRequest,
    *,
    approval_origin_run_id: str | None = None,
) -> ApprovalPolicy:
    approval_store = None
    if request.use_approval_store:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        approval_store = ApprovalPresetStore(request.root)
    return ApprovalPolicy(
        preapproved_call_ids=request.approved_call_ids,
        allow_all_destructive=request.allow_destructive,
        full_access_acknowledged=request.allow_destructive,
        permission_mode=(
            PermissionMode.DANGER_FULL_ACCESS
            if request.allow_destructive
            else request.permission_mode
        ),
        approval_store=approval_store,
        approval_origin_run_id=approval_origin_run_id
        or request.resumed_from
        or request.run_id,
        multi_sig_config=MultiSigQuorumConfig.from_workspace_config(request.root),
    )


def prepare_agent_run(request: RunSetupRequest) -> PreparedAgentRun:
    """Build the shared run object graph for harness entry points."""
    root = Path(request.root).resolve()
    run_store = RunStore(root)
    run_id = request.run_id or f'pending-{uuid4().hex}'

    registry = request.registry or build_workspace_tool_registry(root)
    if request.hook_registry is not None and registry.hook_registry is None:
        registry.hook_registry = request.hook_registry

    plugin_load_failed: list[str] = []
    if request.load_plugins and request.registry is None:
        from teaagent.plugins import load_plugins

        plugin_result = load_plugins(registry)
        plugin_load_failed = list(plugin_result.failed)

    audit = run_store.audit_logger(None if run_id.startswith('pending-') else run_id)
    budget = build_run_budget(
        max_iterations=request.max_iterations,
        max_tool_calls=request.max_tool_calls,
        max_estimated_cost_cents=request.max_estimated_cost_cents,
    )
    approval_policy = build_approval_policy(
        request,
        approval_origin_run_id=request.resumed_from or run_id,
    )

    return PreparedAgentRun(
        root=root,
        run_store=run_store,
        registry=registry,
        audit=audit,
        budget=budget,
        approval_policy=approval_policy,
        run_id=run_id,
        plugin_load_failed=plugin_load_failed,
    )


class AgentService:
    """Thin facade for shared run preparation."""

    def prepare(self, request: RunSetupRequest) -> PreparedAgentRun:
        return prepare_agent_run(request)
