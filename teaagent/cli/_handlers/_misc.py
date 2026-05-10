from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore
from teaagent.intent import clarify_task
from teaagent.llm import available_providers, check_llm_configuration
from teaagent.policy import parse_permission_mode
from teaagent.tui import run_tui
from teaagent.ultrawork import UltraworkStore
from teaagent.workspace_tools import build_workspace_tool_registry


def clarify_command(args: argparse.Namespace) -> int:
    print_json(clarify_task(args.task).to_dict())
    return 0


def start_tui(args: argparse.Namespace) -> int:
    return run_tui(
        database=args.database,
        provider=args.provider,
        model=args.model,
        root=args.root,
        allow_destructive=args.allow_destructive,
        permission_mode=parse_permission_mode(args.permission_mode),
    )


def graphqlite_query(args: argparse.Namespace) -> int:
    store = GraphQLiteGraphStore(GraphQLiteConfig(database=args.database))
    print_json(store.query(args.cypher))
    return 0


def graphqlite_smoke(args: argparse.Namespace) -> int:
    store = GraphQLiteGraphStore(GraphQLiteConfig(database=args.database))
    store.graph.upsert_node('teaagent', {'name': 'TeaAgent'}, label='SmokeTest')
    result = store.query('MATCH (n:SmokeTest) RETURN n.name')
    print_json(result)
    return 0


def graphqlite_migrate(args: argparse.Namespace) -> int:
    from teaagent.graphqlite_production import (
        GraphQLitePersistentStore,
        GraphQLiteProductionConfig,
    )

    store = GraphQLitePersistentStore(
        GraphQLiteProductionConfig(
            database=args.database, auto_index=False, auto_migrate=False
        )
    )
    print_json(store.migration_status())
    return 0


def ultrawork_start_command(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        '-m',
        'teaagent.cli',
        'agent',
        'run',
        args.provider,
        args.task,
        '--root',
        args.root,
        '--heartbeat',
        str(args.heartbeat),
        '--permission-mode',
        args.permission_mode,
    ]
    if args.model:
        command.extend(['--model', args.model])
    record = UltraworkStore(args.root).start(command, label=args.label)
    print_json(record.to_dict())
    return 0


def ultrawork_list_command(args: argparse.Namespace) -> int:
    print_json(UltraworkStore(args.root).list())
    return 0


def ultrawork_show_command(args: argparse.Namespace) -> int:
    try:
        print_json(UltraworkStore(args.root).show(args.worker_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def ultrawork_stop_command(args: argparse.Namespace) -> int:
    try:
        print_json(UltraworkStore(args.root).stop(args.worker_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def workspace_tools_metadata(args: argparse.Namespace) -> int:
    registry = build_workspace_tool_registry(args.root)
    print_json(registry.mcp_metadata())
    return 0


def workspace_openapi_command(args: argparse.Namespace) -> int:
    from teaagent.openapi import generate_openapi_schema

    registry = build_workspace_tool_registry(args.root)
    schema = generate_openapi_schema(
        registry,
        title=args.title,
        version=args.api_version,
        server_url=getattr(args, 'server_url', None) or None,
    )
    print_json(schema)
    return 0


def completion_command(args: argparse.Namespace) -> int:
    if args.shell == 'bash':
        print(
            'complete -W "agent audit clarify completion configure doctor graphqlite mcp memory model tui ultrawork workspace" teaagent'
        )
    elif args.shell == 'zsh':
        print(
            '#compdef teaagent\n_arguments "1: :((agent audit clarify completion configure doctor graphqlite mcp memory model tui ultrawork workspace))"'
        )
    else:
        print(
            'complete -c teaagent -f -a "agent audit clarify completion configure doctor graphqlite mcp memory model tui ultrawork workspace"'
        )
    return 0


def configure_command(args: argparse.Namespace) -> int:
    providers = args.provider or available_providers()
    if not providers:
        print_json({'ok': True, 'message': 'no providers to configure'})
        return 0

    missing = []
    for provider in providers:
        ok, message = check_llm_configuration(provider)
        if not ok:
            missing.append((provider, message))

    if not missing:
        print_json({'ok': True, 'message': 'all providers are already configured'})
        return 0

    env_path = Path.home() / '.teaagent' / 'env'
    env_path.parent.mkdir(parents=True, exist_ok=True)

    if env_path.exists():
        existing = env_path.read_text(encoding='utf-8')
    else:
        existing = ''

    new_exports = ''
    for provider, message in missing:
        env_var = _provider_env_var(provider)
        print(f'Provider {provider}: {message}')
        try:
            key = getpass.getpass(f'  Enter {env_var} (input hidden): ').strip()
        except EOFError:
            print(f'  Skipped {provider} (no input available)')
            continue
        if not key:
            print(f'  Skipped {provider} (empty input)')
            continue
        export_line = f'export {env_var}={key}\n'
        if export_line not in existing:
            new_exports += export_line
            os.environ[env_var] = key

    if not new_exports:
        print_json({'ok': False, 'message': 'no keys were entered, nothing written'})
        return 1

    env_path.write_text(existing + new_exports, encoding='utf-8')
    print_json(
        {
            'ok': True,
            'message': f'wrote {env_path}',
            'hint': f'source {env_path}  # add this to your shell profile for persistence',
        }
    )
    return 0


def _provider_env_var(provider: str) -> str:
    from teaagent.llm._config import PROVIDER_CONFIGS

    config = PROVIDER_CONFIGS.get(provider)
    return config.api_key_env if config else ''


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
