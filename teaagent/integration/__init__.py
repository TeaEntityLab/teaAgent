"""Integration and extension boundary contracts (WS5).

Shared run setup, event streams, approval strategies, storage adapters, and
plugin governance live here so CLI, TUI, plugins, and tests share one harness
surface instead of duplicating orchestration.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    'AgentService',
    'ApprovalPresetStorage',
    'ApprovalStrategy',
    'AuditStorage',
    'CallbackApprovalStrategy',
    'LocalApprovalPresetStorage',
    'LocalAuditStorage',
    'LocalMemoryStorage',
    'LocalRunStorage',
    'MemoryStorage',
    'PluginGovernanceReport',
    'PolicyApprovalStrategy',
    'PreparedAgentRun',
    'RunEvent',
    'RunEventStream',
    'RunEventSubscriber',
    'RunSetupRequest',
    'RunStateSnapshot',
    'RunStorage',
    'RUN_STATE_SCHEMA_VERSION',
    'build_run_state_snapshot',
    'approval_handler_from_strategy',
    'approval_strategy_from_policy',
    'build_approval_policy',
    'build_run_budget',
    'normalize_run_event',
    'prepare_agent_run',
    'replay_run_events',
    'storage_bundle_for_workspace',
    'validate_plugin_tools',
]


def __getattr__(name: str) -> Any:
    if name in {
        'ApprovalStrategy',
        'CallbackApprovalStrategy',
        'PolicyApprovalStrategy',
        'approval_handler_from_strategy',
        'approval_strategy_from_policy',
    }:
        from teaagent.integration import approval_strategy as approval_module

        return getattr(approval_module, name)
    if name in {
        'RunEvent',
        'RunEventStream',
        'RunEventSubscriber',
        'normalize_run_event',
        'replay_run_events',
    }:
        from teaagent.integration import event_stream as event_module

        return getattr(event_module, name)
    if name in {'PluginGovernanceReport', 'validate_plugin_tools'}:
        from teaagent.integration import plugin_governance as plugin_module

        return getattr(plugin_module, name)
    if name in {
        'AgentService',
        'PreparedAgentRun',
        'RunSetupRequest',
        'build_approval_policy',
        'build_run_budget',
        'prepare_agent_run',
    }:
        from teaagent.integration import run_contract as run_module

        return getattr(run_module, name)
    if name in {
        'RunStateSnapshot',
        'RUN_STATE_SCHEMA_VERSION',
        'build_run_state_snapshot',
    }:
        from teaagent.integration import run_state as state_module

        return getattr(state_module, name)
    if name in {
        'ApprovalPresetStorage',
        'AuditStorage',
        'LocalApprovalPresetStorage',
        'LocalAuditStorage',
        'LocalMemoryStorage',
        'LocalRunStorage',
        'MemoryStorage',
        'RunStorage',
        'storage_bundle_for_workspace',
    }:
        from teaagent.integration import storage as storage_module

        return getattr(storage_module, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
