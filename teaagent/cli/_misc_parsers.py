from __future__ import annotations

import argparse
from typing import Callable, Optional

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    _init(subparsers, handlers.get('init'))
    _clarify(subparsers, handlers['clarify'])
    _tui(subparsers, handlers['tui'])
    _configure(subparsers, handlers.get('configure'))
    _doctor(
        subparsers,
        handlers['doctor_graphqlite'],
        handlers['doctor_model'],
        handlers.get('doctor_aigateway'),
        handlers.get('doctor_providers'),
        handlers.get('doctor_project'),
        handlers.get('doctor_mcp'),
        handlers.get('doctor_env_order'),
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
        handlers['ultrawork_logs'],
        handlers['ultrawork_stop'],
    )
    _workspace(subparsers, handlers['workspace_tools'], handlers['workspace_openapi'])


def _init(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'init',
        help='Initialize workspace TeaAgent config (first-time wizard).',
        description='Create .teaagent/config.json and optionally .teaagent/env for provider keys.',
    )
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument(
        '--provider',
        choices=available_providers(),
        default=None,
        help='Default provider to set. If omitted, prompts interactively.',
    )
    p.add_argument(
        '--api-key',
        default=None,
        help='Provider API key. If omitted, prompts interactively (hidden).',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Default permission mode written to config.',
    )
    p.add_argument(
        '--max-iterations',
        type=int,
        default=10,
        help='Default max_iterations written to config.',
    )
    p.add_argument(
        '--max-tool-calls',
        type=int,
        default=10,
        help='Default max_tool_calls written to config.',
    )
    p.add_argument(
        '--write-env',
        action='store_true',
        help='Also write .teaagent/env export line for the selected provider API key.',
    )
    p.set_defaults(func=handler)


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
    p.add_argument(
        '--chat',
        action='store_true',
        default=False,
        help='Start with chat mode enabled.',
    )
    p.set_defaults(func=handler)


def _doctor(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    graphqlite_handler: Callable,
    model_handler: Callable,
    aigateway_handler: Optional[Callable] = None,
    providers_handler: Optional[Callable] = None,
    project_handler: Optional[Callable] = None,
    mcp_handler: Optional[Callable] = None,
    env_order_handler: Optional[Callable] = None,
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
    mdl.add_argument(
        '--wizard',
        action='store_true',
        help='Run interactive setup wizard for this provider.',
    )
    mdl.add_argument(
        '--write-env',
        action='store_true',
        help='When used with --wizard, write exports to .teaagent/env under --root.',
    )
    mdl.add_argument(
        '--root',
        default='.',
        help='Workspace root used by --write-env. Defaults to current directory.',
    )
    mdl.set_defaults(func=model_handler)

    aig = subs.add_parser(
        'aigateway',
        help='Guided check for Cloudflare Workers AI + AI Gateway configuration.',
    )
    aig.add_argument(
        '--wizard',
        action='store_true',
        help='Run interactive setup wizard for AI Gateway environment variables.',
    )
    aig.add_argument(
        '--mode',
        choices=('workers-ai', 'compat'),
        default='workers-ai',
        help='Gateway endpoint mode: workers-ai provider path or OpenAI-compatible /compat path.',
    )
    aig.add_argument(
        '--write-env',
        action='store_true',
        help='When used with --wizard, write exports to .teaagent/env under --root.',
    )
    aig.add_argument(
        '--root',
        default='.',
        help='Workspace root used by --write-env. Defaults to current directory.',
    )
    aig.set_defaults(func=aigateway_handler or model_handler)

    providers = subs.add_parser(
        'providers',
        help='Guided provider readiness checks and optional key setup.',
    )
    providers.add_argument(
        '--wizard',
        action='store_true',
        help='Run interactive provider setup wizard.',
    )
    providers.add_argument(
        '--provider',
        action='append',
        choices=available_providers(),
        default=None,
        help='Provider to configure in wizard mode. Can be repeated. Defaults to all.',
    )
    providers.add_argument(
        '--write-env',
        action='store_true',
        help='When used with --wizard, write configured exports to .teaagent/env under --root.',
    )
    providers.add_argument(
        '--root',
        default='.',
        help='Workspace root used by --write-env. Defaults to current directory.',
    )
    providers.set_defaults(func=providers_handler or model_handler)

    project = subs.add_parser(
        'project',
        help='Guided first-run project readiness wizard.',
    )
    project.add_argument(
        '--wizard',
        action='store_true',
        help='Run interactive project setup wizard.',
    )
    project.add_argument(
        '--root',
        default='.',
        help='Workspace root for generated next steps. Defaults to current directory.',
    )
    project.set_defaults(func=project_handler or model_handler)

    mcp = subs.add_parser(
        'mcp',
        help='Guided MCP server setup checks and launch command generation.',
    )
    mcp.add_argument(
        '--wizard',
        action='store_true',
        help='Run interactive MCP setup wizard.',
    )
    mcp.add_argument(
        '--root',
        default='.',
        help='Workspace root for generated command. Defaults to current directory.',
    )
    mcp.set_defaults(func=mcp_handler or model_handler)

    env_order = subs.add_parser(
        'env-order',
        help='Check global and project env file layering order.',
    )
    env_order.add_argument(
        '--root',
        default='.',
        help='Workspace root to inspect for .teaagent/env. Defaults to current directory.',
    )
    env_order.set_defaults(func=env_order_handler or model_handler)

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
    logs_handler: Callable,
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

    logs = subs.add_parser('logs', help='Show one worker log tail.')
    logs.add_argument('worker_id', help='Worker id to inspect.')
    logs.add_argument('--root', default='.', help='Workspace root.')
    logs.add_argument(
        '--bytes', type=int, default=64_000, help='Maximum log bytes to return.'
    )
    logs.set_defaults(func=logs_handler)

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
