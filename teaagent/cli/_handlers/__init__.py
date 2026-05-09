from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore
from teaagent.intent import clarify_task
from teaagent.llm import LLMMessage, LLMRequest, available_providers
from teaagent.mcp_http import is_loopback_host
from teaagent.mcp_server import serve_mcp_stdio
from teaagent.memory import MemoryCatalog
from teaagent.model_routing import route_model
from teaagent.policy import parse_permission_mode
from teaagent.run_store import RunStore
from teaagent.tui import run_tui
from teaagent.ultrawork import UltraworkStore
from teaagent.workspace_tools import build_workspace_tool_registry

from ._agent import (
    agent_preflight_command as agent_preflight_command,
)
from ._agent import (
    agent_resume_command as agent_resume_command,
)
from ._agent import (
    agent_run_show as agent_run_show,
)
from ._agent import (
    agent_run_task as agent_run_task,
)
from ._agent import (
    agent_runs_list as agent_runs_list,
)
from ._agent import (
    agent_status_command as agent_status_command,
)


def doctor_graphqlite(args: argparse.Namespace) -> int:
    ok, message = args._check_graphqlite(args.database)  # type: ignore[attr-defined]
    print(json.dumps({'ok': ok, 'message': message}, sort_keys=True))
    return 0 if ok else 1


def doctor_all(args: argparse.Namespace) -> int:
    checks: dict[str, Any] = {}
    gql_ok, gql_message = args._check_graphqlite(args.database)  # type: ignore[attr-defined]
    checks['graphqlite'] = {'ok': gql_ok, 'message': gql_message}
    provider_results = []
    for provider in args.provider or available_providers():
        ok, message = args._check_llm(provider)  # type: ignore[attr-defined]
        provider_results.append({'provider': provider, 'ok': ok, 'message': message})
    checks['providers'] = provider_results
    ok = gql_ok and all(item['ok'] for item in provider_results)
    print_json({'ok': ok, 'checks': checks})
    return 0 if ok else 1


def clarify_command(args: argparse.Namespace) -> int:
    print_json(clarify_task(args.task).to_dict())
    return 0


def memory_add_command(args: argparse.Namespace) -> int:
    entry = MemoryCatalog(args.root).add(args.content, tags=tuple(args.tag))
    print_json(entry.to_dict())
    return 0


def memory_list_command(args: argparse.Namespace) -> int:
    print_json(
        [entry.to_dict() for entry in MemoryCatalog(args.root).list(limit=args.limit)]
    )
    return 0


def memory_search_command(args: argparse.Namespace) -> int:
    print_json(
        [
            entry.to_dict()
            for entry in MemoryCatalog(args.root).search(args.query, limit=args.limit)
        ]
    )
    return 0


def memory_show_command(args: argparse.Namespace) -> int:
    print_json(MemoryCatalog(args.root).show(args.memory_id).to_dict())
    return 0


def doctor_model(args: argparse.Namespace) -> int:
    ok, message = args._check_llm(args.provider)  # type: ignore[attr-defined]
    print(
        json.dumps(
            {'ok': ok, 'message': message, 'provider': args.provider}, sort_keys=True
        )
    )
    return 0 if ok else 1


def model_providers(_args: argparse.Namespace) -> int:
    print_json(available_providers())
    return 0


def model_smoke(args: argparse.Namespace) -> int:
    adapter = args._adapter_factory(args.provider, model=args.model)  # type: ignore[attr-defined]
    response = adapter.complete(
        LLMRequest(
            messages=[LLMMessage(role='user', content=args.prompt)],
            max_tokens=args.max_tokens,
        )
    )
    print_json(
        {
            'provider': response.provider,
            'model': response.model,
            'content': response.content,
        }
    )
    return 0


def model_conformance(args: argparse.Namespace) -> int:
    report = args._run_model_conformance(  # type: ignore[attr-defined]
        args.provider,
        prompt=args.prompt,
        expected_content=args.expect if args.expect else None,
        max_tokens=args.max_tokens,
        model=args.model,
    )
    print_json(report.as_dict())
    return 0 if report.ok else 1


def model_route(args: argparse.Namespace) -> int:
    print_json(
        route_model(args.task, provider=args.provider, model=args.model).to_dict()
    )
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


def mcp_serve_command(args: argparse.Namespace) -> int:
    from teaagent.oauth21 import OAuth21AuthorizationServer

    registry = build_workspace_tool_registry(args.root)
    if args.http:
        oauth_server = None
        if args.oauth_issuer and args.oauth_signing_key:
            oauth_server = OAuth21AuthorizationServer(
                signing_key=args.oauth_signing_key,
                issuer=args.oauth_issuer,
                token_ttl=args.oauth_token_ttl,
            )
            for spec in args.oauth_client or []:
                parts = spec.split(':', 2)
                if len(parts) != 3:
                    print(
                        f'Invalid --oauth-client format: {spec} (expected ID:SECRET:REDIRECT_URI)',
                        file=sys.stderr,
                    )
                    return 1
                oauth_server.register_client(*parts)
        elif args.oauth_issuer or args.oauth_signing_key:
            print(
                'Both --oauth-issuer and --oauth-signing-key must be provided to enable OAuth.',
                file=sys.stderr,
            )
            return 1
        if (
            not is_loopback_host(args.host)
            and not args.auth_token
            and oauth_server is None
        ):
            print(
                'Refusing to serve MCP HTTP on a non-loopback host without --auth-token or OAuth.',
                file=sys.stderr,
            )
            return 1
        return args._serve_mcp_http(  # type: ignore[attr-defined]
            registry,
            host=args.host,
            port=args.port,
            auth_token=args.auth_token,
            allowed_origins=args.allowed_origin or None,
            oauth_server=oauth_server,
        )
    return serve_mcp_stdio(registry)


def workspace_tools_metadata(args: argparse.Namespace) -> int:
    registry = build_workspace_tool_registry(args.root)
    print_json(registry.mcp_metadata())
    return 0


def completion_command(args: argparse.Namespace) -> int:
    if args.shell == 'bash':
        print(
            'complete -W "agent audit clarify completion doctor graphqlite mcp memory model tui ultrawork workspace" teaagent'
        )
    elif args.shell == 'zsh':
        print(
            '#compdef teaagent\n_arguments "1: :((agent audit clarify completion doctor graphqlite mcp memory model tui ultrawork workspace))"'
        )
    else:
        print(
            'complete -c teaagent -f -a "agent audit clarify completion doctor graphqlite mcp memory model tui ultrawork workspace"'
        )
    return 0


def audit_list_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json([summary.to_dict() for summary in store.list_runs(limit=args.limit)])
    return 0


def audit_show_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        print_json(store.show_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def audit_prune_command(args: argparse.Namespace) -> int:
    if args.days is None and args.keep is None and not args.all:
        print_json(
            {
                'status': 'error',
                'message': 'audit prune requires --days, --keep, or --all',
            }
        )
        return 1
    store = RunStore(args.root)
    cutoff = time.time() - (args.days * 86400) if args.days is not None else None
    run_paths = sorted(
        store.store_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True
    )
    keep = set(run_paths[: args.keep]) if args.keep is not None else set()
    deleted: list[str] = []
    for path in run_paths:
        if path in keep:
            continue
        if cutoff is not None and path.stat().st_mtime >= cutoff:
            continue
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + '.lock').unlink(missing_ok=True)
        deleted.append(path.name)
    print_json({'count': len(deleted), 'deleted': deleted})
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
