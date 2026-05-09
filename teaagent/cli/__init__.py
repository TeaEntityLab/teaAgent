from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from teaagent import __version__
from teaagent.cli._handlers import (
    agent_preflight_command,
    agent_resume_command,
    agent_run_show,
    agent_run_task,
    agent_runs_list,
    agent_status_command,
    audit_list_command,
    audit_prune_command,
    audit_show_command,
    clarify_command,
    completion_command,
    doctor_all,
    doctor_graphqlite,
    doctor_model,
    graphqlite_query,
    graphqlite_smoke,
    mcp_serve_command,
    memory_add_command,
    memory_list_command,
    memory_search_command,
    memory_show_command,
    model_conformance,
    model_providers,
    model_route,
    model_smoke,
    start_tui,
    ultrawork_list_command,
    ultrawork_show_command,
    ultrawork_start_command,
    ultrawork_stop_command,
    workspace_tools_metadata,
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
    args = parser.parse_args(argv)
    args._adapter_factory = _adapter_factory or create_llm_adapter  # type: ignore[attr-defined]
    args._serve_mcp_http = _serve_mcp_http or serve_mcp_http  # type: ignore[attr-defined]
    args._check_graphqlite = _check_graphqlite or check_graphqlite_runtime  # type: ignore[attr-defined]
    args._check_llm = _check_llm or check_llm_configuration  # type: ignore[attr-defined]
    args._run_model_conformance = _run_model_conformance or run_model_conformance  # type: ignore[attr-defined]
    apply_config_defaults(args)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    from teaagent.cli._agent_parsers import register as register_agent
    from teaagent.cli._mcp_parsers import register as register_mcp
    from teaagent.cli._memory_parsers import register as register_memory
    from teaagent.cli._misc_parsers import register as register_misc
    from teaagent.cli._model_parsers import register as register_model

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
    subparsers = parser.add_subparsers(dest='command', required=True)

    register_misc(
        subparsers,
        {
            'clarify': clarify_command,
            'tui': start_tui,
            'doctor_graphqlite': doctor_graphqlite,
            'doctor_model': doctor_model,
            'doctor_all': doctor_all,
            'graphqlite_query': graphqlite_query,
            'graphqlite_smoke': graphqlite_smoke,
            'ultrawork_start': ultrawork_start_command,
            'ultrawork_list': ultrawork_list_command,
            'ultrawork_show': ultrawork_show_command,
            'ultrawork_stop': ultrawork_stop_command,
            'workspace_tools': workspace_tools_metadata,
            'completion': completion_command,
            'audit_list': audit_list_command,
            'audit_show': audit_show_command,
            'audit_prune': audit_prune_command,
        },
    )
    register_memory(
        subparsers,
        {
            'add': memory_add_command,
            'list': memory_list_command,
            'search': memory_search_command,
            'show': memory_show_command,
        },
    )
    register_agent(
        subparsers,
        {
            'run': agent_run_task,
            'preflight': agent_preflight_command,
            'resume': agent_resume_command,
            'status': agent_status_command,
            'runs': agent_runs_list,
            'show': agent_run_show,
        },
    )
    register_model(
        subparsers,
        {
            'providers': model_providers,
            'smoke': model_smoke,
            'conformance': model_conformance,
            'route': model_route,
        },
    )
    register_mcp(
        subparsers,
        {
            'serve': mcp_serve_command,
        },
    )

    return parser


def apply_config_defaults(args: argparse.Namespace) -> None:
    config_path = resolve_config_path(getattr(args, 'config', None))
    if config_path is None:
        return
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
        'provider': 'gpt',
        'permission_mode': PermissionMode.PROMPT.value,
    }
    for key, value in data.items():
        if not hasattr(args, key):
            continue
        if getattr(args, key) == defaults.get(key):
            setattr(args, key, value)


def resolve_config_path(explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        return Path(explicit)
    candidate = Path('.teaagent') / 'config.json'
    return candidate if candidate.is_file() else None
