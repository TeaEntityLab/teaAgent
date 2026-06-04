from __future__ import annotations

import argparse
from typing import Callable, Optional

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def _deprecation_warning(args: argparse.Namespace) -> int:
    """Handler for deprecated commands."""
    print('This command is deprecated and not yet implemented.')
    return 1


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    handlers: dict[str, Callable],
) -> None:
    _init(subparsers, handlers.get('init'))
    _setup(subparsers, handlers.get('setup'))
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
        git_sandbox_handler=handlers.get('doctor_git_sandbox'),
        selftest_handler=handlers.get('doctor_selftest'),
    )
    _selftest_top_level(subparsers, handlers.get('doctor_selftest'))
    _completion(subparsers, handlers['completion'])
    _audit(
        subparsers,
        handlers['audit_list'],
        handlers['audit_show'],
        handlers['audit_prune'],
        serve_handler=handlers.get('audit_serve'),
        verify_handler=handlers.get('audit_verify'),
        export_handler=handlers.get('audit_export'),
    )
    _env(
        subparsers,
        handlers.get('env_provision'),
        handlers.get('env_verify'),
        handlers.get('env_lock'),
    )
    _graphqlite(
        subparsers,
        handlers['graphqlite_query'],
        handlers['graphqlite_smoke'],
        migrate_handler=handlers.get('graphqlite_migrate'),
    )
    _code_ontology(
        subparsers,
        handlers.get('code_ontology_build'),
        handlers.get('code_ontology_query'),
    )
    _experiment(
        subparsers,
        handlers.get('experiment_list'),
        handlers.get('experiment_compare'),
        handlers.get('experiment_select'),
        handlers.get('experiment_cancel'),
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
    _sync(
        subparsers,
        handlers.get('sync_export'),
        handlers.get('sync_import'),
        handlers.get('sync_status'),
        handlers.get('sync_signature_relay_serve'),
        handlers.get('sync_signature_submit'),
    )
    _replay(
        subparsers,
        handlers.get('replay_list'),
        handlers.get('replay_steps'),
        handlers.get('replay_fork'),
        handlers.get('replay_resume'),
    )


def _add_workspace_bootstrap_args(p: argparse.ArgumentParser) -> None:
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
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Default context profile written to config.',
    )
    p.add_argument(
        '--heartbeat',
        type=float,
        default=0.0,
        help='Default heartbeat interval (seconds) written to config.',
    )
    p.add_argument(
        '--daily-cost-cap-cents',
        type=int,
        default=0,
        help='Daily estimated cost cap in cents (0 disables).',
    )
    p.add_argument(
        '--human',
        action='store_true',
        help='Print a beginner-friendly summary instead of JSON.',
    )


def _init(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'init',
        help='Initialize workspace TeaAgent config (legacy bootstrap).',
        description='Create .teaagent/config.json and optionally .teaagent/env for provider keys.',
    )
    _add_workspace_bootstrap_args(p)
    p.add_argument(
        '--wizard',
        action='store_true',
        help='Run the guided first-session setup flow (same as `teaagent setup`).',
    )
    p.set_defaults(func=handler)


def _setup(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'setup',
        help='Guided first-session setup (recommended).',
        description=(
            'Configure provider, workspace defaults, AGENTS.md, env order checks, '
            'and return a safe next command.'
        ),
    )
    _add_workspace_bootstrap_args(p)
    p.set_defaults(func=handler)


def _clarify(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]  # argparse private class lacks generic type param
    p = subparsers.add_parser(
        'clarify', help='Score a task for ambiguity before running an agent.'
    )
    p.add_argument('task', help='Task to clarify.')
    p.set_defaults(func=handler)


def _tui(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]  # argparse private class lacks generic type param
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
    p.add_argument(
        '--setup',
        action='store_true',
        help='Run the guided first-session setup wizard before the REPL.',
    )
    p.add_argument(
        '--write-env',
        action='store_true',
        help='With --setup, also write .teaagent/env for the provider API key.',
    )
    p.set_defaults(func=handler)


def _doctor(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    graphqlite_handler: Callable,
    model_handler: Callable,
    aigateway_handler: Optional[Callable] = None,
    providers_handler: Optional[Callable] = None,
    project_handler: Optional[Callable] = None,
    mcp_handler: Optional[Callable] = None,
    env_order_handler: Optional[Callable] = None,
    all_handler: Optional[Callable] = None,
    migration_handler: Optional[Callable] = None,
    git_sandbox_handler: Optional[Callable] = None,
    selftest_handler: Optional[Callable] = None,
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
    all_checks.add_argument(
        '--repair',
        action='store_true',
        help='Automatically fix common issues (file permissions, database migrations).',
    )
    all_checks.add_argument(
        '--root',
        default='.',
        help='Workspace root for repair operations. Defaults to current directory.',
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

    git_sandbox = subs.add_parser(
        'git-sandbox',
        help='Check for orphaned git sandbox branches from incomplete agent runs.',
    )
    git_sandbox.add_argument(
        '--prune',
        action='store_true',
        help='Delete orphaned sandbox branches after confirmation.',
    )
    git_sandbox.add_argument(
        '--root',
        default='.',
        help='Workspace root to inspect for orphaned branches. Defaults to current directory.',
    )
    git_sandbox.set_defaults(func=git_sandbox_handler or model_handler)

    selftest = subs.add_parser('selftest', help='Run harness self-tests.')
    selftest.add_argument(
        '--security',
        action='store_true',
        help='Run governance/security self-test (default).',
    )
    selftest.add_argument(
        '--maturity',
        action='store_true',
        help='Show maturity-matrix guidance only.',
    )
    selftest.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    selftest.set_defaults(func=selftest_handler or model_handler)


def _selftest_top_level(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    handler: Optional[Callable],
) -> None:
    p = subparsers.add_parser('selftest', help='Run harness self-tests (alias).')
    p.add_argument('--security', action='store_true', help='Run security self-test.')
    p.add_argument('--maturity', action='store_true')
    p.add_argument('--root', default='.')
    p.set_defaults(func=handler)


def _configure(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
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


def _completion(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]  # argparse private class lacks generic type param
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
    verify_handler: Optional[Callable] = None,
    export_handler: Optional[Callable] = None,
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
    show_cmd.add_argument(
        '--with-reasoning',
        action='store_true',
        help='Include model reasoning alongside tool call events.',
    )
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

    if verify_handler is not None:
        verify_cmd = subs.add_parser(
            'verify',
            help='Verify cryptographic audit chain integrity and generate attestation.',
        )
        verify_cmd.add_argument('--root', default='.', help='Workspace root.')
        verify_cmd.add_argument(
            '--signature',
            default=None,
            help='Path to SSH/GPG key for signing attestation (e.g., ~/.ssh/id_ed25519).',
        )
        verify_cmd.set_defaults(func=verify_handler)

    if export_handler is not None:
        export_cmd = subs.add_parser(
            'export',
            help='Export a signed compliance bundle for a run.',
        )
        export_cmd.add_argument('run_id', help='Run id to export.')
        export_cmd.add_argument('--root', default='.', help='Workspace root.')
        export_cmd.add_argument(
            '--output',
            '-o',
            default=None,
            help='Output file path. Prints to stdout if omitted.',
        )
        export_cmd.add_argument(
            '--compact',
            action='store_true',
            help='Compact JSON output (no indentation).',
        )
        export_cmd.add_argument(
            '--skip-chain-verify',
            action='store_true',
            help='Skip hash-chain verification.',
        )
        export_cmd.set_defaults(func=export_handler)


def _graphqlite(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
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


def _code_ontology(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    build_handler: Optional[Callable] = None,
    query_handler: Optional[Callable] = None,
) -> None:
    code_ontology = subparsers.add_parser(
        'code-ontology', help='Build and query code ontology graph.'
    )
    subs = code_ontology.add_subparsers(dest='code_ontology_command', required=True)

    build = subs.add_parser('build', help='Build code ontology from source files.')
    build.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    build.add_argument(
        '--extensions',
        default='.py',
        help='File extensions to parse (comma-separated). Defaults to .py.',
    )
    build.set_defaults(func=build_handler)

    query = subs.add_parser('query', help='Query code ontology for dependencies.')
    query.add_argument('entity', help='Entity name to query (class, function, etc.).')
    query.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    query.add_argument(
        '--direction',
        choices=['upstream', 'downstream', 'both'],
        default='both',
        help='Dependency direction: upstream (callers), downstream (callees), or both.',
    )
    query.set_defaults(func=query_handler)


def _ultrawork(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    start_handler: Callable,
    list_handler: Callable,
    show_handler: Callable,
    logs_handler: Callable,
    stop_handler: Callable,
) -> None:
    import sys

    def _deprecation_warning(args: argparse.Namespace) -> int:
        print(
            '[TeaAgent WARNING] "ultrawork" commands are deprecated. '
            'Please use "teaagent background" or "teaagent agent run --background" instead.',
            file=sys.stderr,
        )
        # Route to the appropriate handler based on subcommand
        cmd = args.ultrawork_command
        if cmd == 'start':
            return start_handler(args)
        elif cmd == 'list':
            return list_handler(args)
        elif cmd == 'show':
            return show_handler(args)
        elif cmd == 'logs':
            return logs_handler(args)
        elif cmd == 'stop':
            return stop_handler(args)
        return 1

    ultrawork = subparsers.add_parser(
        'ultrawork',
        help='DEPRECATED: Manage detached background agent workers (use background instead).',
        description='DEPRECATED: Use "teaagent background" or "teaagent agent run --background" instead.',
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
    start.set_defaults(func=_deprecation_warning)

    lst = subs.add_parser('list', help='List background workers.')
    lst.add_argument('--root', default='.', help='Workspace root.')
    lst.set_defaults(func=_deprecation_warning)

    show = subs.add_parser('show', help='Show one worker record.')
    show.add_argument('worker_id', help='Worker id to inspect.')
    show.add_argument('--root', default='.', help='Workspace root.')
    show.set_defaults(func=_deprecation_warning)

    logs = subs.add_parser('logs', help='Show one worker log tail.')
    logs.add_argument('worker_id', help='Worker id to inspect.')
    logs.add_argument('--root', default='.', help='Workspace root.')
    logs.add_argument(
        '--bytes', type=int, default=64_000, help='Maximum log bytes to return.'
    )
    logs.set_defaults(func=_deprecation_warning)

    stop = subs.add_parser('stop', help='Stop a running worker.')
    stop.add_argument('worker_id', help='Worker id to stop.')
    stop.add_argument('--root', default='.', help='Workspace root.')
    stop.set_defaults(func=_deprecation_warning)


def _workspace(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
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


def _experiment(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    list_handler: Optional[Callable],
    compare_handler: Optional[Callable],
    select_handler: Optional[Callable],
    cancel_handler: Optional[Callable],
) -> None:
    experiment = subparsers.add_parser(
        'experiment', help='Manage parallel sandbox experiments.'
    )
    subs = experiment.add_subparsers(dest='experiment_command', required=True)

    list_cmd = subs.add_parser('list', help='List all sandbox branches.')
    list_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    list_cmd.set_defaults(func=list_handler or _deprecation_warning)

    compare = subs.add_parser('compare', help='Compare experimental branches.')
    compare.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    compare.add_argument(
        '--run-id',
        required=True,
        help='Run ID for the experiment.',
    )
    compare.add_argument(
        '--options',
        required=True,
        help='Comma-separated list of options (e.g., opt1,opt2,opt3).',
    )
    compare.add_argument(
        '--run-tests',
        action='store_true',
        help='Run test suite on each branch for quality matrix comparison.',
    )
    compare.add_argument(
        '--test-command',
        default='pytest -xvs',
        help='Test command to run (default: pytest -xvs).',
    )
    compare.add_argument(
        '--test-timeout',
        type=int,
        default=300,
        help='Test timeout in seconds per branch (default: 300).',
    )
    compare.set_defaults(func=compare_handler or _deprecation_warning)

    select = subs.add_parser(
        'select', help='Select and merge the best experimental branch.'
    )
    select.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    select.add_argument(
        '--run-id',
        required=True,
        help='Run ID for the experiment.',
    )
    select.add_argument(
        '--options',
        required=True,
        help='Comma-separated list of options (e.g., opt1,opt2,opt3).',
    )
    select.add_argument(
        '--select',
        required=True,
        help='Option to select and merge.',
    )
    select.add_argument(
        '--squash',
        action='store_true',
        help='Squash commits when merging.',
    )
    select.add_argument(
        '--conflict-provider',
        default=None,
        help='LLM provider for automatic conflict resolution (e.g., openai, anthropic).',
    )
    select.add_argument(
        '--conflict-model',
        default=None,
        help='Model name for automatic conflict resolution.',
    )
    select.add_argument(
        '--no-self-healing',
        action='store_true',
        help='Disable LSP self-healing for conflict resolution.',
    )
    select.set_defaults(func=select_handler or _deprecation_warning)

    cancel = subs.add_parser('cancel', help='Cancel and delete experimental branches.')
    cancel.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    cancel.add_argument(
        '--run-id',
        help='Run ID for the experiment (optional for orphaned cleanup).',
    )
    cancel.add_argument(
        '--options',
        help='Comma-separated list of options (optional for orphaned cleanup).',
    )
    cancel.set_defaults(func=cancel_handler or _deprecation_warning)


def _sync(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    export_handler: Optional[Callable],
    import_handler: Optional[Callable],
    status_handler: Optional[Callable],
    signature_relay_serve_handler: Optional[Callable] = None,
    signature_submit_handler: Optional[Callable] = None,
) -> None:
    """Register sync subcommands."""
    sync_parser = subparsers.add_parser(
        'sync', help='Federated multi-agent graph synchronization'
    )
    subs = sync_parser.add_subparsers(dest='sync_command', required=True)

    export_cmd = subs.add_parser('export', help='Export sync message for P2P transfer')
    export_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    export_cmd.add_argument(
        '--agent-id',
        required=True,
        help='Agent ID for the sync message.',
    )
    export_cmd.add_argument(
        '--output',
        required=True,
        help='Output path for sync message JSON file.',
    )
    export_cmd.set_defaults(func=export_handler or _deprecation_warning)

    import_cmd = subs.add_parser('import', help='Import and apply sync message')
    import_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    import_cmd.add_argument(
        '--agent-id',
        required=True,
        help='Local agent ID receiving the sync.',
    )
    import_cmd.add_argument(
        '--input',
        required=True,
        help='Input path for sync message JSON file.',
    )
    import_cmd.set_defaults(func=import_handler or _deprecation_warning)

    status_cmd = subs.add_parser('status', help='Show federated sync status')
    status_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    status_cmd.add_argument(
        '--agent-id',
        required=True,
        help='Agent ID to check status for.',
    )
    status_cmd.set_defaults(func=status_handler or _deprecation_warning)

    sig_relay = subs.add_parser(
        'signature-relay',
        help='HTTP relay for WAN multi-sig approval requests and signatures',
    )
    sig_subs = sig_relay.add_subparsers(
        dest='signature_relay_command', required=True, help='Signature relay commands'
    )
    sig_serve = sig_subs.add_parser('serve', help='Start signature relay HTTP server')
    sig_serve.add_argument('--host', default='127.0.0.1')
    sig_serve.add_argument('--port', type=int, default=8791)
    sig_serve.add_argument('--api-token', help='Bearer token for relay requests')
    sig_serve.add_argument('--api-token-file', help='JSON relay token file')
    sig_serve.add_argument('--tls-cert', help='TLS certificate PEM')
    sig_serve.add_argument('--tls-key', help='TLS private key PEM')
    sig_serve.add_argument('--tls-client-ca', help='Client CA PEM for mTLS')
    sig_serve.add_argument(
        '--rate-limit-calls',
        type=int,
        default=120,
        help='Max POSTs per token per window (0 disables)',
    )
    sig_serve.add_argument(
        '--rate-limit-window',
        type=float,
        default=60.0,
        help='Rate limit window seconds',
    )
    sig_serve.set_defaults(func=signature_relay_serve_handler or _deprecation_warning)

    sig_submit = sig_subs.add_parser(
        'submit', help='Submit a peer signature to a signature relay'
    )
    sig_submit.add_argument(
        '--relay-url', help='Relay base URL if --submit-url omitted'
    )
    sig_submit.add_argument(
        '--submit-url',
        default='',
        help='Full POST URL (defaults to {relay-url}/api/v1/approval-signatures)',
    )
    sig_submit.add_argument('--request-id', required=True)
    sig_submit.add_argument('--peer-id', required=True)
    sig_submit.add_argument('--signature', required=True)
    sig_submit.add_argument('--ssh-key-id', help='SSH key id metadata')
    sig_submit.add_argument('--api-token', help='Bearer token')
    sig_submit.set_defaults(func=signature_submit_handler or _deprecation_warning)


def _replay(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    list_handler: Optional[Callable],
    steps_handler: Optional[Callable],
    fork_handler: Optional[Callable],
    resume_handler: Optional[Callable],
) -> None:
    """Register replay subcommands."""
    replay_parser = subparsers.add_parser(
        'replay', help='Time-travel replay and debugging'
    )
    subs = replay_parser.add_subparsers(dest='replay_command', required=True)

    list_cmd = subs.add_parser('list', help='List available runs for replay')
    list_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    list_cmd.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of runs to list.',
    )
    list_cmd.set_defaults(func=list_handler or _deprecation_warning)

    steps_cmd = subs.add_parser('steps', help='List steps in a run')
    steps_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    steps_cmd.add_argument(
        '--run-id',
        required=True,
        help='Run ID to inspect.',
    )
    steps_cmd.set_defaults(func=steps_handler or _deprecation_warning)

    fork_cmd = subs.add_parser('fork', help='Fork a new branch at a specific step')
    fork_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    fork_cmd.add_argument(
        '--run-id',
        required=True,
        help='Run ID to fork from.',
    )
    fork_cmd.add_argument(
        '--step',
        type=int,
        required=True,
        help='Step number to fork at.',
    )
    fork_cmd.add_argument(
        '--branch-name',
        required=True,
        help='Name for the new replay branch.',
    )
    fork_cmd.set_defaults(func=fork_handler or _deprecation_warning)

    resume_cmd = subs.add_parser(
        'resume', help='Resume execution from a replay checkpoint'
    )
    resume_cmd.add_argument(
        '--root',
        default='.',
        help='Workspace root. Defaults to current directory.',
    )
    resume_cmd.add_argument(
        '--branch-name',
        required=True,
        help='Branch name to resume.',
    )
    resume_cmd.set_defaults(func=resume_handler or _deprecation_warning)


def _env(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]  # argparse private class lacks generic type param
    provision_handler: Callable | None,
    verify_handler: Callable | None,
    lock_handler: Callable | None,
) -> None:
    """Register environment subcommands."""
    env_parser = subparsers.add_parser(
        'env', help='Hermetic environment provisioning and verification'
    )
    subs = env_parser.add_subparsers(dest='env_command', required=True)

    provision_cmd = subs.add_parser(
        'provision', help='Provision hermetic environment from teaagent.toml'
    )
    provision_cmd.add_argument('--root', default='.', help='Workspace root.')
    provision_cmd.set_defaults(func=provision_handler)

    verify_cmd = subs.add_parser(
        'verify', help='Verify environment compliance against lockfile'
    )
    verify_cmd.add_argument('--root', default='.', help='Workspace root.')
    verify_cmd.set_defaults(func=verify_handler)

    lock_cmd = subs.add_parser(
        'lock', help='Generate lockfile from current environment'
    )
    lock_cmd.add_argument('--root', default='.', help='Workspace root.')
    lock_cmd.set_defaults(func=lock_handler)
