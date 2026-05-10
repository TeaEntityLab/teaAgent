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
    _configure(subparsers, handlers.get('configure'))
    _doctor(
        subparsers,
        handlers['doctor_graphqlite'],
        handlers['doctor_model'],
        handlers['doctor_all'],
        migration_handler=handlers.get('doctor_migration'),
    )
    _completion(subparsers, handlers['completion'])
    _audit(
        subparsers,
        handlers['audit_list'],
        handlers['audit_show'],
        handlers['audit_prune'],
        serve_handler=handlers.get('audit_serve'),
    )
    _graphqlite(
        subparsers,
        handlers['graphqlite_query'],
        handlers['graphqlite_smoke'],
        migrate_handler=handlers.get('graphqlite_migrate'),
    )
    _ultrawork(
        subparsers,
        handlers['ultrawork_start'],
        handlers['ultrawork_list'],
        handlers['ultrawork_show'],
        handlers['ultrawork_stop'],
    )
    _workspace(subparsers, handlers['workspace_tools'], handlers['workspace_openapi'])


def _clarify(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'clarify', help='Score a task for ambiguity before running an agent.'
    )
    p.add_argument('task', help='Task to clarify.')
    p.set_defaults(func=handler)


def _tui(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'tui',
        help='Start an interactive terminal UI.',
        description='Start an interactive terminal UI.',
    )
    p.add_argument(
        '--database',
        default=':memory:',
        help='SQLite database path. Defaults to :memory:.',
    )
    p.add_argument(
        '--provider',
        default='gpt',
        choices=available_providers(),
        help='Default model provider for ask commands.',
    )
    p.add_argument(
        '--model', default=None, help='Default model override for ask commands.'
    )
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
    migration_handler: Optional[Callable] = None,
) -> None:
    doctor = subparsers.add_parser('doctor', help='Run environment checks.')
    subs = doctor.add_subparsers(dest='doctor_command', required=True)

    gql = subs.add_parser('graphqlite', help='Check GraphQLite runtime availability.')
    gql.add_argument(
        '--database',
        default=':memory:',
        help='SQLite database path. Defaults to :memory:.',
    )
    gql.set_defaults(func=graphqlite_handler)

    mdl = subs.add_parser('model', help='Check model provider configuration.')
    mdl.add_argument(
        'provider', choices=available_providers(), help='Model provider to check.'
    )
    mdl.set_defaults(func=model_handler)

    all_checks = subs.add_parser('all', help='Run all environment checks.')
    all_checks.add_argument(
        '--database',
        default=':memory:',
        help='SQLite database path. Defaults to :memory:.',
    )
    all_checks.add_argument(
        '--provider',
        action='append',
        choices=available_providers(),
        default=None,
        help='Provider to check. Can be repeated. Defaults to all providers.',
    )
    all_checks.set_defaults(func=all_handler or graphqlite_handler)

    migration = subs.add_parser(
        'migration', help='Check schema migration status for a SQLite store.'
    )
    migration.add_argument(
        '--store',
        default=None,
        metavar='PATH',
        help='SQLite database path to inspect for migration status.',
    )
    migration.set_defaults(func=migration_handler or graphqlite_handler)


def _configure(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'configure',
        help='Interactively set provider API keys.',
        description='Check which providers are missing API keys and prompt for each one.',
    )
    p.add_argument(
        '--provider',
        action='append',
        choices=available_providers(),
        default=None,
        help='Provider to configure. Can be repeated. Defaults to all providers.',
    )
    p.set_defaults(func=handler)


def _completion(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser('completion', help='Print a shell completion snippet.')
    p.add_argument(
        'shell', choices=['bash', 'zsh', 'fish'], help='Shell to generate for.'
    )
    p.set_defaults(func=handler)


def _audit(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    list_handler: Callable,
    show_handler: Callable,
    prune_handler: Callable,
    serve_handler: Optional[Callable] = None,
) -> None:
    audit = subparsers.add_parser('audit', help='Inspect and prune run audit logs.')
    subs = audit.add_subparsers(dest='audit_command', required=True)

    list_cmd = subs.add_parser('list', help='List persisted audit runs.')
    list_cmd.add_argument('--root', default='.', help='Workspace root.')
    list_cmd.add_argument('--limit', type=int, default=20, help='Maximum runs to list.')
    list_cmd.set_defaults(func=list_handler)

    show_cmd = subs.add_parser('show', help='Show one audit JSONL run.')
    show_cmd.add_argument('run_id', help='Run id to show.')
    show_cmd.add_argument('--root', default='.', help='Workspace root.')
    show_cmd.set_defaults(func=show_handler)

    prune_cmd = subs.add_parser('prune', help='Delete old audit JSONL runs.')
    prune_cmd.add_argument('--root', default='.', help='Workspace root.')
    prune_cmd.add_argument(
        '--days', type=int, default=None, help='Delete runs older than N days.'
    )
    prune_cmd.add_argument(
        '--keep', type=int, default=None, help='Always keep latest N runs.'
    )
    prune_cmd.add_argument(
        '--all',
        action='store_true',
        help='Delete all audit runs not protected by --keep.',
    )
    prune_cmd.set_defaults(func=prune_handler)

    if serve_handler is not None:
        serve_cmd = subs.add_parser(
            'serve', help='Start a local web viewer for audit logs.'
        )
        serve_cmd.add_argument('--root', default='.', help='Workspace root.')
        serve_cmd.add_argument(
            '--host',
            default='127.0.0.1',
            help='Bind host. Defaults to 127.0.0.1.',
        )
        serve_cmd.add_argument(
            '--port', type=int, default=8080, help='Bind port. Default 8080.'
        )
        serve_cmd.set_defaults(func=serve_handler)


def _graphqlite(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    query_handler: Callable,
    smoke_handler: Callable,
    migrate_handler: Optional[Callable] = None,
) -> None:
    graphqlite = subparsers.add_parser('graphqlite', help='Run GraphQLite operations.')
    subs = graphqlite.add_subparsers(dest='graphqlite_command', required=True)

    query = subs.add_parser('query', help='Execute a Cypher query against GraphQLite.')
    query.add_argument('cypher', help='Cypher query to execute.')
    query.add_argument(
        '--database',
        default=':memory:',
        help='SQLite database path. Defaults to :memory:.',
    )
    query.set_defaults(func=query_handler)

    smoke = subs.add_parser(
        'smoke', help='Create a node and run a real GraphQLite query.'
    )
    smoke.add_argument(
        '--database',
        default=':memory:',
        help='SQLite database path. Defaults to :memory:.',
    )
    smoke.set_defaults(func=smoke_handler)

    if migrate_handler is not None:
        migrate = subs.add_parser(
            'migrate', help='Show GraphQLite schema migration status.'
        )
        migrate.add_argument(
            '--database',
            default=':memory:',
            help='SQLite database path. Defaults to :memory:.',
        )
        migrate.set_defaults(func=migrate_handler)


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
    start.add_argument(
        'provider', choices=available_providers(), help='Model provider to use.'
    )
    start.add_argument('task', help='Task for the agent to perform.')
    start.add_argument('--root', default='.', help='Workspace root.')
    start.add_argument('--model', default=None, help='Override model name.')
    start.add_argument(
        '--heartbeat',
        type=float,
        default=10.0,
        help='Heartbeat interval seconds for the worker.',
    )
    start.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for workspace tools.',
    )
    start.add_argument(
        '--label', default=None, help='Optional human label for this worker.'
    )
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


def _workspace(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    openapi_handler: Callable,
) -> None:
    workspace = subparsers.add_parser('workspace', help='Inspect workspace tool pack.')
    subs = workspace.add_subparsers(dest='workspace_command', required=True)

    tools = subs.add_parser('tools', help='List workspace tool metadata.')
    tools.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    tools.set_defaults(func=handler)

    openapi = subs.add_parser(
        'openapi',
        help='Generate an OpenAPI 3.1 schema for all registered workspace tools.',
    )
    openapi.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    openapi.add_argument(
        '--title',
        default='TeaAgent Tools API',
        help='API title in the OpenAPI info object.',
    )
    openapi.add_argument(
        '--api-version',
        default='1.0.0',
        help='API version in the OpenAPI info object.',
    )
    openapi.add_argument(
        '--server-url',
        default=None,
        metavar='URL',
        help='Server URL to embed in the OpenAPI servers list (optional).',
    )
    openapi.set_defaults(func=openapi_handler)
