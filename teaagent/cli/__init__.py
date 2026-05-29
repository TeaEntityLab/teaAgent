from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional, cast

from teaagent import __version__
from teaagent.cli._handlers import (
    agent_attach_command,
    agent_card_command,
    agent_daily_command,
    agent_plan_command,
    agent_preflight_command,
    agent_resume_command,
    agent_run_show,
    agent_run_task,
    agent_runs_export,
    agent_runs_list,
    agent_runs_replay,
    agent_runs_trace,
    agent_status_command,
    agent_subagent_review_apply_command,
    agent_subagent_review_check_command,
    agent_subagent_review_list_command,
    agent_subagent_review_show_command,
    agent_undo_command,
    approval_approve_command,
    approval_audit_command,
    approval_check_command,
    approval_deny_command,
    approval_doctor_command,
    approval_explain_command,
    approval_grant_command,
    approval_list_command,
    approval_next_command,
    approval_pending_command,
    approval_preset_command,
    approval_revoke_command,
    audit_list_command,
    audit_prune_command,
    audit_serve_command,
    audit_show_command,
    audit_verify_command,
    automation_add_command,
    automation_delete_command,
    automation_list_command,
    automation_pause_command,
    automation_promote_command,
    automation_resume_command,
    automation_run_command,
    automation_serve_command,
    automation_show_command,
    automation_status_command,
    automation_template_command,
    automation_tick_command,
    background_list_command,
    background_show_command,
    chat_command,
    ci_review_command,
    clarify_command,
    cloud_cancel_command,
    cloud_capabilities_command,
    cloud_list_command,
    cloud_show_command,
    cloud_submit_command,
    completion_command,
    configure_command,
    consensus_config_set_command,
    consensus_history_command,
    consensus_peers_activate_command,
    consensus_peers_add_command,
    consensus_peers_deactivate_command,
    consensus_peers_list_command,
    consensus_peers_remove_command,
    consensus_request_command,
    consensus_status_command,
    consensus_vote_command,
    daily_journal_command,
    doctor_aigateway,
    doctor_all,
    doctor_env_order,
    doctor_git_sandbox,
    doctor_graphqlite,
    doctor_mcp,
    doctor_migration_command,
    doctor_model,
    doctor_project,
    doctor_providers,
    doctor_selftest_command,
    env_lock_command,
    env_provision_command,
    env_verify_command,
    experiment_cancel,
    experiment_compare,
    experiment_list,
    experiment_select,
    gateway_list_command,
    gateway_start_command,
    graphqlite_migrate,
    graphqlite_query,
    graphqlite_smoke,
    guidance_command,
    init_command,
    interactive_review_command,
    mcp_serve_command,
    mcp_trust_allow_command,
    mcp_trust_deny_command,
    mcp_trust_inspect_command,
    mcp_trust_list_command,
    memory_add_command,
    memory_failures_auto_invalidate_command,
    memory_failures_invalidate_command,
    memory_failures_list_command,
    memory_failures_prune_command,
    memory_failures_review_command,
    memory_failures_show_command,
    memory_list_command,
    memory_search_command,
    memory_show_command,
    model_capabilities,
    model_conformance,
    model_providers,
    model_route,
    model_smoke,
    plugin_list_command,
    plugin_show_command,
    plugin_verify_command,
    recall_command,
    recipes_list_command,
    recipes_run_command,
    replay_fork,
    replay_list,
    replay_resume,
    replay_steps,
    sandbox_check_compatibility_command,
    sandbox_check_wasm_command,
    sandbox_monitor_command,
    sandbox_route_command,
    session_list_command,
    session_resume_command,
    session_show_command,
    setup_command,
    skill_candidate_eval_command,
    skill_candidate_install_command,
    skill_candidate_list_command,
    skill_candidate_propose_command,
    skill_candidate_review_command,
    skill_candidate_show_command,
    skill_explain_command,
    skill_install_marketplace_command,
    skill_marketplace_list_command,
    skill_publish_command,
    skill_search_command,
    skill_verify_tsb_command,
    start_tui,
    status_short_command,
    sync_export,
    sync_import,
    sync_status,
    tool_inspect_command,
    tool_lint_command,
    tool_list_command,
    ultrawork_list_command,
    ultrawork_logs_command,
    ultrawork_show_command,
    ultrawork_start_command,
    ultrawork_stop_command,
    watch_command,
    workspace_openapi_command,
    workspace_tools_metadata,
    yesterday_command,
)
from teaagent.graphqlite_store import (
    check_graphqlite_runtime,
)
from teaagent.llm import (
    check_llm_configuration,
    create_llm_adapter,
)
from teaagent.llm_conformance import (
    run_model_conformance,  # noqa: F401  # kept for test patches
)
from teaagent.mcp_http import serve_mcp_http
from teaagent.policy import PermissionMode

_TOP_LEVEL_AGENT_COMMANDS = frozenset(
    {'run', 'ask', 'daily', 'resume', 'preflight', 'plan'}
)
_AGENT_PROVIDER_COMMANDS = frozenset({'run', 'daily', 'resume', 'preflight', 'plan'})


def _resolve_agent_command(args: argparse.Namespace) -> Optional[str]:
    command = getattr(args, 'command', None)
    if command in {'run', 'ask'}:
        return 'run'
    if command in _TOP_LEVEL_AGENT_COMMANDS - {'run', 'ask'}:
        return str(command)
    if command == 'agent':
        agent_command = getattr(args, 'agent_command', None)
        if agent_command in _AGENT_PROVIDER_COMMANDS:
            return str(agent_command)
    return None


def _expand_argv(argv: Optional[list[str]]) -> Optional[list[str]]:
    return argv


def main(
    argv: Optional[list[str]] = None,
    *,
    _adapter_factory: Any = None,
    _serve_mcp_http: Any = None,
    _check_graphqlite: Any = None,
    _check_llm: Any = None,
    _run_model_conformance: Any = None,
) -> int:
    parser = build_parser()
    raw_argv = argv if argv is not None else sys.argv[1:]
    expanded_argv = _expand_argv(raw_argv)

    args = parser.parse_args(expanded_argv)
    if getattr(args, 'command', None) is None:
        new_argv = raw_argv + ['chat']
        args = parser.parse_args(new_argv)
    args._adapter_factory = _adapter_factory or create_llm_adapter  # type: ignore[attr-defined]
    args._serve_mcp_http = _serve_mcp_http or serve_mcp_http  # type: ignore[attr-defined]
    args._check_graphqlite = _check_graphqlite or check_graphqlite_runtime  # type: ignore[attr-defined]
    args._check_llm = _check_llm or check_llm_configuration  # type: ignore[attr-defined]
    args._run_model_conformance = _run_model_conformance or run_model_conformance  # type: ignore[attr-defined]
    apply_config_defaults(args)
    _normalize_optional_provider_args(args)
    _require_provider_for_agent_commands(args)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    from teaagent.cli._agent_parsers import register as register_agent
    from teaagent.cli._cloud_parsers import register as register_cloud
    from teaagent.cli._consensus_parsers import register as register_consensus
    from teaagent.cli._ergonomics_parsers import register as register_ergonomics
    from teaagent.cli._gateway_parsers import register as register_gateway
    from teaagent.cli._mcp_parsers import register as register_mcp
    from teaagent.cli._memory_parsers import register as register_memory
    from teaagent.cli._misc_parsers import register as register_misc
    from teaagent.cli._model_parsers import register as register_model
    from teaagent.cli._plugin_parsers import register as register_plugin
    from teaagent.cli._sandbox_parsers import register as register_sandbox
    from teaagent.cli._skill_parsers import register as register_skill
    from teaagent.cli._tool_parsers import register as register_tool

    parser = argparse.ArgumentParser(
        prog='teaagent', description='TeaAgent harness utilities.'
    )
    parser.add_argument(
        '--version', action='version', version=f'teaagent {__version__}'
    )
    parser.add_argument(
        '--config',
        default=None,
        help='JSON config file. Defaults to .teaagent/config.json when present.',
    )
    parser.add_argument(
        '--profile',
        default=None,
        help='Profile name under the config file profiles object.',
    )
    subparsers = parser.add_subparsers(dest='command', required=False)

    register_misc(
        subparsers,
        {
            'clarify': clarify_command,
            'tui': start_tui,
            'configure': configure_command,
            'doctor_graphqlite': doctor_graphqlite,
            'doctor_model': doctor_model,
            'doctor_aigateway': doctor_aigateway,
            'doctor_providers': doctor_providers,
            'doctor_project': doctor_project,
            'doctor_mcp': doctor_mcp,
            'doctor_env_order': doctor_env_order,
            'doctor_all': doctor_all,
            'graphqlite_query': graphqlite_query,
            'graphqlite_smoke': graphqlite_smoke,
            'graphqlite_migrate': graphqlite_migrate,
            'ultrawork_start': ultrawork_start_command,
            'ultrawork_list': ultrawork_list_command,
            'ultrawork_logs': ultrawork_logs_command,
            'ultrawork_show': ultrawork_show_command,
            'experiment_list': experiment_list,
            'experiment_compare': experiment_compare,
            'experiment_select': experiment_select,
            'experiment_cancel': experiment_cancel,
            'sync_export': sync_export,
            'sync_import': sync_import,
            'sync_status': sync_status,
            'replay_list': replay_list,
            'replay_steps': replay_steps,
            'replay_fork': replay_fork,
            'replay_resume': replay_resume,
            'ultrawork_stop': ultrawork_stop_command,
            'workspace_tools': workspace_tools_metadata,
            'workspace_openapi': workspace_openapi_command,
            'completion': completion_command,
            'init': init_command,
            'setup': setup_command,
            'audit_list': audit_list_command,
            'audit_show': audit_show_command,
            'audit_prune': audit_prune_command,
            'audit_serve': audit_serve_command,
            'audit_verify': audit_verify_command,
            'doctor_migration': doctor_migration_command,
            'doctor_git_sandbox': doctor_git_sandbox,
            'doctor_selftest': doctor_selftest_command,
            'env_provision': env_provision_command,
            'env_verify': env_verify_command,
            'env_lock': env_lock_command,
        },
    )
    register_memory(
        subparsers,
        {
            'add': memory_add_command,
            'list': memory_list_command,
            'search': memory_search_command,
            'show': memory_show_command,
            'failures_list': memory_failures_list_command,
            'failures_show': memory_failures_show_command,
            'failures_invalidate': memory_failures_invalidate_command,
            'failures_prune': memory_failures_prune_command,
            'failures_review': memory_failures_review_command,
            'failures_auto_invalidate': memory_failures_auto_invalidate_command,
        },
    )
    register_skill(
        subparsers,
        {
            'candidate_propose': skill_candidate_propose_command,
            'candidate_eval': skill_candidate_eval_command,
            'candidate_list': skill_candidate_list_command,
            'candidate_show': skill_candidate_show_command,
            'candidate_review': skill_candidate_review_command,
            'candidate_install': skill_candidate_install_command,
            'explain': skill_explain_command,
            'publish': skill_publish_command,
            'search': skill_search_command,
            'marketplace-list': skill_marketplace_list_command,
            'install-from-marketplace': skill_install_marketplace_command,
            'publish_tsb': skill_publish_command,
            'verify_tsb': skill_verify_tsb_command,
        },
    )
    register_plugin(
        subparsers,
        {
            'list': plugin_list_command,
            'show': plugin_show_command,
            'verify': plugin_verify_command,
        },
    )
    register_tool(
        subparsers,
        {
            'list': tool_list_command,
            'inspect': tool_inspect_command,
            'lint': tool_lint_command,
        },
    )
    register_consensus(
        subparsers,
        {
            'peers_list': consensus_peers_list_command,
            'peers_add': consensus_peers_add_command,
            'peers_remove': consensus_peers_remove_command,
            'peers_activate': consensus_peers_activate_command,
            'peers_deactivate': consensus_peers_deactivate_command,
            'config_set': consensus_config_set_command,
            'status': consensus_status_command,
            'history': consensus_history_command,
            'request': consensus_request_command,
            'vote': consensus_vote_command,
        },
    )
    register_sandbox(
        subparsers,
        {
            'route': sandbox_route_command,
            'monitor': sandbox_monitor_command,
            'check_wasm': sandbox_check_wasm_command,
            'check_compatibility': sandbox_check_compatibility_command,
        },
    )
    from teaagent.cli._agent_parsers import register_top_level_agent_aliases

    register_top_level_agent_aliases(
        subparsers,
        cast(
            dict[str, Callable[..., Any]],
            {
                'run': agent_run_task,
                'daily': agent_daily_command,
                'preflight': agent_preflight_command,
                'plan': agent_plan_command,
                'resume': agent_resume_command,
                'runs': {
                    'list': agent_runs_list,
                    'show': agent_run_show,
                    'trace': agent_runs_trace,
                    'export': agent_runs_export,
                    'replay': agent_runs_replay,
                },
                'chat': chat_command,
            },
        ),
    )
    register_agent(
        subparsers,
        cast(
            dict[str, Callable[..., Any]],
            {
                'run': agent_run_task,
                'preflight': agent_preflight_command,
                'plan': agent_plan_command,
                'daily': agent_daily_command,
                'resume': agent_resume_command,
                'undo': agent_undo_command,
                'status': agent_status_command,
                'runs': {
                    'list': agent_runs_list,
                    'show': agent_run_show,
                    'trace': agent_runs_trace,
                    'export': agent_runs_export,
                    'replay': agent_runs_replay,
                },
                'show': agent_run_show,
                'card': agent_card_command,
                'attach': agent_attach_command,
                'chat': chat_command,
                'interactive_review': interactive_review_command,
                'subagent_review_list': agent_subagent_review_list_command,
                'subagent_review_show': agent_subagent_review_show_command,
                'subagent_review_check': agent_subagent_review_check_command,
                'subagent_review_apply': agent_subagent_review_apply_command,
                'automation_add': automation_add_command,
                'automation_list': automation_list_command,
                'automation_show': automation_show_command,
                'automation_pause': automation_pause_command,
            'automation_resume': automation_resume_command,
            'automation_delete': automation_delete_command,
            'automation_promote': automation_promote_command,
            'automation_run': automation_run_command,
            'automation_tick': automation_tick_command,
            'automation_serve': automation_serve_command,
            'automation_status': automation_status_command,
            'automation_template': automation_template_command,
            },
        ),
    )
    register_ergonomics(
        subparsers,
        {
            'yesterday': yesterday_command,
            'recall': recall_command,
            'status_short': status_short_command,
            'background_list': background_list_command,
            'background_show': background_show_command,
            'session_list': session_list_command,
            'session_show': session_show_command,
            'session_resume': session_resume_command,
            'recipes_list': recipes_list_command,
            'recipes_run': recipes_run_command,
            'approval_list': approval_list_command,
            'approval_check': approval_check_command,
            'approval_explain': approval_explain_command,
            'approval_revoke': approval_revoke_command,
            'approval_grant': approval_grant_command,
            'approval_deny': approval_deny_command,
            'approval_audit': approval_audit_command,
            'approval_pending': approval_pending_command,
            'approval_approve': approval_approve_command,
            'approval_preset': approval_preset_command,
            'approval_doctor': approval_doctor_command,
            'approval_next': approval_next_command,
            'guidance': guidance_command,
            'ci_review': ci_review_command,
            'watch': watch_command,
            'daily_journal': daily_journal_command,
        },
    )
    register_model(
        subparsers,
        {
            'providers': model_providers,
            'capabilities': model_capabilities,
            'smoke': model_smoke,
            'conformance': model_conformance,
            'route': model_route,
        },
    )
    register_mcp(
        subparsers,
        {
            'serve': mcp_serve_command,
            'trust_list': mcp_trust_list_command,
            'trust_inspect': mcp_trust_inspect_command,
            'trust_allow': mcp_trust_allow_command,
            'trust_deny': mcp_trust_deny_command,
        },
    )
    register_cloud(
        subparsers,
        {
            'submit': cloud_submit_command,
            'list': cloud_list_command,
            'show': cloud_show_command,
            'cancel': cloud_cancel_command,
            'capabilities': cloud_capabilities_command,
        },
    )
    register_gateway(
        subparsers,
        {
            'start': gateway_start_command,
            'list': gateway_list_command,
        },
    )

    return parser


def _normalize_optional_provider_args(args: argparse.Namespace) -> None:
    agent_command = _resolve_agent_command(args)
    if agent_command is None or agent_command not in _AGENT_PROVIDER_COMMANDS:
        return
    from teaagent.llm import available_providers

    providers = set(available_providers())
    provider = getattr(args, 'provider', None)
    if not provider or provider in providers:
        return
    if agent_command == 'resume':
        args.run_id = provider
        args.provider = None
        return
    task = getattr(args, 'task', None)
    if task:
        raise SystemExit(f'unknown provider: {provider}')
    args.task = provider
    args.provider = None


def _require_provider_for_agent_commands(args: argparse.Namespace) -> None:
    agent_command = _resolve_agent_command(args)
    if agent_command is None or agent_command not in _AGENT_PROVIDER_COMMANDS:
        return
    from teaagent.ergonomics.workspace_defaults import (
        apply_workspace_defaults_to_namespace,
    )
    from teaagent.llm import available_providers

    providers = set(available_providers())
    if getattr(args, 'provider', None) and args.provider not in providers:
        raise SystemExit(f'unknown provider: {args.provider}')
    apply_workspace_defaults_to_namespace(
        args, root=getattr(args, 'root', '.'), require_provider=True
    )


def apply_config_defaults(args: argparse.Namespace) -> None:
    if getattr(args, 'command', None) in {'init', 'setup'}:
        return
    from teaagent.ergonomics.workspace_defaults import (
        apply_workspace_defaults_to_namespace,
        load_workspace_defaults,
    )

    root = getattr(args, 'root', '.')
    config_path = resolve_config_path(getattr(args, 'config', None))
    if config_path is None:
        apply_workspace_defaults_to_namespace(args, root=root)
        return
    if config_path.suffix == '.toml':
        data = {
            k: v
            for k, v in load_workspace_defaults(root).items()
            if v is not None and k != 'root'
        }
    else:
        data = json.loads(config_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise SystemExit('--config must contain a JSON object')
    profile = getattr(args, 'profile', None)
    if profile:
        profiles = data.get('profiles')
        if not isinstance(profiles, dict) or profile not in profiles:
            raise SystemExit(f"profile '{profile}' not found in {config_path}")
        selected = profiles[profile]
        if not isinstance(selected, dict):
            raise SystemExit(f"profile '{profile}' must be a JSON object")
        merged = {k: v for k, v in data.items() if k != 'profiles'}
        merged.update(selected)
        data = merged
    defaults = {
        'root': '.',
        'model': None,
        'permission_mode': PermissionMode.PROMPT.value,
    }
    command = getattr(args, 'command', None)
    doctor_command = getattr(args, 'doctor_command', None)
    for key, value in data.items():
        if not hasattr(args, key):
            continue
        # Keep `doctor all` semantics stable: without explicit --provider,
        # check all providers.
        if command == 'doctor' and doctor_command == 'all' and key == 'provider':
            continue
        if getattr(args, key) == defaults.get(key):
            setattr(args, key, value)


def resolve_config_path(explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        return Path(explicit)
    json_candidate = Path('.teaagent') / 'config.json'
    if json_candidate.is_file():
        return json_candidate
    toml_candidate = Path('.teaagent') / 'config.toml'
    return toml_candidate if toml_candidate.is_file() else None
