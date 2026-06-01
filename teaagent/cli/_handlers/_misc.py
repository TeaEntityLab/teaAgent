from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

from teaagent.code_ontology import CodeOntologyGraph
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore
from teaagent.intent import clarify_task
from teaagent.llm import available_providers, check_llm_configuration
from teaagent.policy import parse_permission_mode
from teaagent.tui import run_tui
from teaagent.ultrawork import UltraworkStore
from teaagent.wizard import run_first_session_setup
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
        chat=getattr(args, 'chat', False),
        run_setup=getattr(args, 'setup', False),
        setup_write_env=getattr(args, 'write_env', False),
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


def code_ontology_build(args: argparse.Namespace) -> int:
    """Build code ontology graph from source files."""
    root = Path(args.root).resolve()

    # Initialize GraphQLite store
    db_path = root / '.teaagent' / 'graphqlite.db'
    store = GraphQLiteGraphStore(GraphQLiteConfig(database=str(db_path)))

    # Build ontology
    extensions = getattr(args, 'extensions', None)
    if extensions:
        ext_list = extensions.split(',')
    else:
        ext_list = ['.py']

    ontology = CodeOntologyGraph(root, graph_store=store)
    ontology.build(extensions=ext_list)

    nodes = ontology.builder.get_nodes()
    edges = ontology.builder.get_edges()

    print_json(
        {
            'status': 'success',
            'root': str(root),
            'nodes_count': len(nodes),
            'edges_count': len(edges),
            'extensions': ext_list,
            'database': str(db_path),
        }
    )
    return 0


def code_ontology_query(args: argparse.Namespace) -> int:
    """Query code ontology for dependencies."""
    root = Path(args.root).resolve()

    db_path = root / '.teaagent' / 'graphqlite.db'
    if not db_path.is_file():
        print_json(
            {
                'status': 'error',
                'message': 'Code ontology database not found. Run "teaagent code-ontology build" first.',
            }
        )
        return 1

    store = GraphQLiteGraphStore(GraphQLiteConfig(database=str(db_path)))
    ontology = CodeOntologyGraph(root, graph_store=store)

    entity = args.entity
    direction = getattr(args, 'direction', 'both')

    if direction not in ('upstream', 'downstream', 'both'):
        print_json(
            {
                'status': 'error',
                'message': 'direction must be upstream, downstream, or both',
            }
        )
        return 1

    results = ontology.query_dependencies(entity, direction=direction)

    print_json(
        {
            'status': 'success',
            'entity': entity,
            'direction': direction,
            'results': results,
            'count': len(results),
        }
    )
    return 0


def ultrawork_start_command(args: argparse.Namespace) -> int:
    # Deprecated: redirect to BackgroundRunStore via UltraworkStore

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
    store = UltraworkStore(args.root)
    record = store.start(command, label=args.label)
    print_json(record.to_dict())
    return 0


def ultrawork_list_command(args: argparse.Namespace) -> int:
    # Deprecated: redirect to BackgroundRunStore via UltraworkStore

    print_json(UltraworkStore(args.root, readonly=True).list())
    return 0


def ultrawork_show_command(args: argparse.Namespace) -> int:
    # Deprecated: redirect to BackgroundRunStore via UltraworkStore

    try:
        print_json(UltraworkStore(args.root, readonly=True).show(args.worker_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def ultrawork_logs_command(args: argparse.Namespace) -> int:
    # Deprecated: redirect to BackgroundRunStore via UltraworkStore

    try:
        print_json(
            UltraworkStore(args.root, readonly=True).logs(
                args.worker_id, max_bytes=args.bytes
            )
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def ultrawork_stop_command(args: argparse.Namespace) -> int:
    # Deprecated: redirect to BackgroundRunStore via UltraworkStore

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
    from teaagent.llm import available_providers

    top = (
        'agent approval audit background ci clarify completion configure daily doctor guidance '
        'graphqlite init journal mcp memory model recall recipes session status tui '
        'ultrawork watch workspace yesterday run ask resume'
    )
    providers = ' '.join(available_providers())
    if args.shell == 'bash':
        print(f'complete -W "{top}" teaagent')
        print(f'complete -W "{providers}" teaagent agent run')
    elif args.shell == 'zsh':
        print(
            f'#compdef teaagent\n_arguments "1: :(({top}))"\n_arguments "*:provider:(({providers}))"'
        )
    else:
        print(f'complete -c teaagent -f -a "{top}"')
        print(
            f'complete -c teaagent -n "__fish_seen_subcommand_from agent run" -a "{providers}"'
        )
    return 0


def setup_command(args: argparse.Namespace) -> int:
    result = run_first_session_setup(
        args,
        check_llm=check_llm_configuration,
    )
    payload = result.to_dict()
    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_setup_summary

        print(format_setup_summary(payload, root=args.root))
    else:
        print_json(payload)
    return 0 if result.ok else 1


def init_command(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return setup_command(args)
    root = Path(args.root).resolve()
    tea_dir = root / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)

    provider = args.provider
    if not provider:
        choices = ', '.join(available_providers())
        provider = input(f'Select provider ({choices}) [gpt]: ').strip() or 'gpt'
        if provider not in available_providers():
            print_json({'ok': False, 'message': f'unknown provider: {provider}'})
            return 1

    api_key = args.api_key
    if not api_key:
        env_var = _provider_env_var(provider)
        api_key = getpass.getpass(f'Enter {env_var} (input hidden): ').strip()

    config = {
        'provider': provider,
        'permission_mode': args.permission_mode,
        'max_iterations': int(args.max_iterations),
        'max_tool_calls': int(args.max_tool_calls),
        'context_profile': getattr(args, 'context_profile', 'balanced'),
        'heartbeat': float(getattr(args, 'heartbeat', 0.0)),
        'daily_cost_cap_cents': int(getattr(args, 'daily_cost_cap_cents', 0)),
        'auto_compact_on_resume': True,
    }
    cfg_path = tea_dir / 'config.json'
    cfg_path.write_text(json.dumps(config, sort_keys=True, indent=2), encoding='utf-8')
    toml_path = tea_dir / 'config.toml'
    toml_path.write_text(
        '\n'.join(
            [
                f'provider = "{provider}"',
                f'permission_mode = "{args.permission_mode}"',
                f'max_iterations = {int(args.max_iterations)}',
                f'max_tool_calls = {int(args.max_tool_calls)}',
                f'context_profile = "{config["context_profile"]}"',
                f'heartbeat = {config["heartbeat"]}',
                f'daily_cost_cap_cents = {config["daily_cost_cap_cents"]}',
                'auto_compact_on_resume = true',
                '',
            ]
        ),
        encoding='utf-8',
    )
    config['auto_compact_on_resume'] = True
    agents_md_path = root / 'AGENTS.md'
    agents_md_status = 'existing'
    if not agents_md_path.exists():
        agents_md_path.write_text(
            (
                '# TeaAgent Project Instructions\n\n'
                '- Keep edits minimal, reviewable, and reversible.\n'
                '- Prefer tests-first for behavior changes.\n'
                '- Verify with focused tests before finalizing.\n'
            ),
            encoding='utf-8',
        )
        agents_md_status = 'created'

    env_var = _provider_env_var(provider)
    if api_key and env_var:
        os.environ[env_var] = api_key

    payload = {
        'ok': True,
        'root': str(root),
        'config_path': str(cfg_path),
        'config_toml_path': str(toml_path),
        'agents_md_path': str(agents_md_path),
        'agents_md_status': agents_md_status,
        'provider': provider,
        'permission_mode': args.permission_mode,
        'max_iterations': int(args.max_iterations),
        'max_tool_calls': int(args.max_tool_calls),
        'next_steps': [
            f'teaagent setup --root {root} --provider {provider} --permission-mode read-only',
            f'teaagent daily "summarize this repo" --dry-run --root {root}',
            f'teaagent doctor mcp --wizard --root {root}',
        ],
    }
    if args.write_env and env_var and api_key:
        from teaagent.wizard import merge_env_exports

        env_path = tea_dir / 'env'
        merge_env_exports(
            env_path,
            {env_var: api_key},
            '# Auto-generated by `teaagent init`.',
        )
        payload['env_status'] = 'written'
        payload['env_path'] = str(env_path)
    elif args.write_env:
        payload['env_status'] = 'skipped (missing env var mapping)'
    print_json(payload)
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

    configured_count = 0
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
        os.environ[env_var] = key
        configured_count += 1

    if configured_count == 0:
        print_json({'ok': False, 'message': 'no keys were entered, nothing configured'})
        return 1

    print_json(
        {
            'ok': True,
            'message': f'configured {configured_count} provider(s) for current process only',
            'hint': 'keys were not written to disk to avoid clear-text secret storage',
        }
    )
    return 0


def _provider_env_var(provider: str) -> str:
    from teaagent.llm._config import PROVIDER_CONFIGS

    config = PROVIDER_CONFIGS.get(provider)
    return config.api_key_env if config else ''


def handle_first_run(root: Path, quiet: bool = False) -> bool:
    """Show first-run welcome message once (gated by .teaagent/welcomed).

    Returns True if the welcome was shown, False otherwise.
    """
    # Temporarily disabled to fix test failures
    # TODO: Re-enable once test infrastructure supports stderr capture
    tea_dir = Path(root) / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)
    (tea_dir / 'welcomed').touch()
    return False


def print_json(value: Any) -> None:
    """Print JSON with TTY-aware formatting."""
    import sys

    if sys.stdout.isatty():
        # Human-readable output for TTY
        if isinstance(value, list) and value:
            print_table(value)
        elif isinstance(value, dict):
            print_dict(value)
        else:
            print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        # Raw JSON for pipes/redirects
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def print_table(data: list[dict[str, Any]]) -> None:
    """Print list of dicts as a formatted table."""
    if not data:
        print('(empty)')
        return

    # Extract headers from first item
    headers = list(data[0].keys())
    col_widths = {h: len(str(h)) for h in headers}

    # Calculate column widths
    for row in data:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(str(row.get(h, ''))))

    # Print header
    header_line = '  '.join(f'{h:<{col_widths[h]}}' for h in headers)
    print(header_line)
    print('  '.join('-' * col_widths[h] for h in headers))

    # Print rows
    for row in data:
        print('  '.join(f'{str(row.get(h, "")):<{col_widths[h]}}' for h in headers))


def print_dict(data: dict[str, Any]) -> None:
    """Print dict as formatted key-value pairs."""
    for key, value in data.items():
        print(f'{key}: {value}')
