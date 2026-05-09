from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore
from teaagent.intent import clarify_task
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


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
