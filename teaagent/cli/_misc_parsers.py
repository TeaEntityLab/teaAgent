from __future__ import annotations

import argparse
from typing import Callable, Optional

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    _clarify(subparsers, handlers['clarify'])
    _tui(subparsers, handlers['tui'])
    _doctor(
        subparsers,
        handlers['doctor_graphqlite'],
        handlers['doctor_model'],
        handlers['doctor_all'],
    )
    _completion(subparsers, handlers['completion'])
    _graphqlite(subparsers, handlers['graphqlite_query'], handlers['graphqlite_smoke'])
    _ultrawork(
        subparsers,
        handlers['ultrawork_start'],
        handlers['ultrawork_list'],
        handlers['ultrawork_show'],
        handlers['ultrawork_stop'],
    )
    _workspace(subparsers, handlers['workspace_tools'])


def _clarify(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser('clarify', help='Score a task for ambiguity before running an agent.')
    p.add_argument('task', help='Task to clarify.')
    p.set_defaults(func=handler)


def _tui(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'tui',
        help='Start an interactive terminal UI.',
        description='Start an interactive terminal UI.',
    )
    p.add_argument(
        '--database', default=':memory:', help='SQLite database path. Defaults to :memory:.'
    )
    p.add_argument(
        '--provider',
        default='gpt',
        choices=available_providers(),
        help='Default model provider for ask commands.',
    )
    p.add_argument('--model', default=None, help='Default model override for ask commands.')
    p.add_argument('--root', default='.', help='Workspace root for ask commands.')
    p.add_argument(
        '--allow-destructive',
        action='store_true',
        help='Allow destructive tools for ask commands.',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for ask commands.',
    )
    p.set_defaults(func=handler)


def _doctor(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    graphqlite_handler: Callable,
    model_handler: Callable,
    all_handler: Optional[Callable] = None,
) -> None:
    doctor = subparsers.add_parser('doctor', help='Run environment checks.')
    subs = doctor.add_subparsers(dest='doctor_command', required=True)

    gql = subs.add_parser('graphqlite', help='Check GraphQLite runtime availability.')
    gql.add_argument(
        '--database', default=':memory:', help='SQLite database path. Defaults to :memory:.'
    )
    gql.set_defaults(func=graphqlite_handler)

    mdl = subs.add_parser('model', help='Check model provider configuration.')
    mdl.add_argument('provider', choices=available_providers(), help='Model provider to check.')
    mdl.set_defaults(func=model_handler)

    all_checks = subs.add_parser('all', help='Run all environment checks.')
    all_checks.add_argument(
        '--database', default=':memory:', help='SQLite database path. Defaults to :memory:.'
    )
    all_checks.add_argument(
        '--provider',
        action='append',
        choices=available_providers(),
        default=None,
        help='Provider to check. Can be repeated. Defaults to all providers.',
    )
    all_checks.set_defaults(func=all_handler or graphqlite_handler)


def _completion(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser('completion', help='Print a shell completion snippet.')
    p.add_argument('shell', choices=['bash', 'zsh', 'fish'], help='Shell to generate for.')
    p.set_defaults(func=handler)


def _graphqlite(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    query_handler: Callable,
    smoke_handler: Callable,
) -> None:
    graphqlite = subparsers.add_parser('graphqlite', help='Run GraphQLite operations.')
    subs = graphqlite.add_subparsers(dest='graphqlite_command', required=True)

    query = subs.add_parser('query', help='Execute a Cypher query against GraphQLite.')
    query.add_argument('cypher', help='Cypher query to execute.')
    query.add_argument(
        '--database', default=':memory:', help='SQLite database path. Defaults to :memory:.'
    )
    query.set_defaults(func=query_handler)

    smoke = subs.add_parser('smoke', help='Create a node and run a real GraphQLite query.')
    smoke.add_argument(
        '--database', default=':memory:', help='SQLite database path. Defaults to :memory:.'
    )
    smoke.set_defaults(func=smoke_handler)


def _ultrawork(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    start_handler: Callable,
    list_handler: Callable,
    show_handler: Callable,
    stop_handler: Callable,
) -> None:
    ultrawork = subparsers.add_parser(
        'ultrawork', help='Manage detached background agent workers.'
    )
    subs = ultrawork.add_subparsers(dest='ultrawork_command', required=True)

    start = subs.add_parser('start', help='Start one detached background agent run.')
    start.add_argument('provider', choices=available_providers(), help='Model provider to use.')
    start.add_argument('task', help='Task for the agent to perform.')
    start.add_argument('--root', default='.', help='Workspace root.')
    start.add_argument('--model', default=None, help='Override model name.')
    start.add_argument(
        '--heartbeat', type=float, default=10.0, help='Heartbeat interval seconds for the worker.'
    )
    start.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for workspace tools.',
    )
    start.add_argument('--label', default=None, help='Optional human label for this worker.')
    start.set_defaults(func=start_handler)

    lst = subs.add_parser('list', help='List background workers.')
    lst.add_argument('--root', default='.', help='Workspace root.')
    lst.set_defaults(func=list_handler)

    show = subs.add_parser('show', help='Show one worker record.')
    show.add_argument('worker_id', help='Worker id to inspect.')
    show.add_argument('--root', default='.', help='Workspace root.')
    show.set_defaults(func=show_handler)

    stop = subs.add_parser('stop', help='Stop a running worker.')
    stop.add_argument('worker_id', help='Worker id to stop.')
    stop.add_argument('--root', default='.', help='Workspace root.')
    stop.set_defaults(func=stop_handler)


def _workspace(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    workspace = subparsers.add_parser('workspace', help='Inspect workspace tool pack.')
    subs = workspace.add_subparsers(dest='workspace_command', required=True)

    tools = subs.add_parser('tools', help='List workspace tool metadata.')
    tools.add_argument('--root', default='.', help='Workspace root. Defaults to current directory.')
    tools.set_defaults(func=handler)
