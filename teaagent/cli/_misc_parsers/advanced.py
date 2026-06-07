from __future__ import annotations

import argparse
from typing import Callable, Optional

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def _graphqlite(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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
            'Please use "teaagent agent run "<task>"" for autonomous runs or '
            '"teaagent agent interactive-review <run_id>" for run inspection instead.',
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
        help='DEPRECATED: Manage detached background agent workers (use current agent surfaces instead).',
        description=(
            'DEPRECATED: Use "teaagent agent run "<task>"" for autonomous runs '
            'or "teaagent agent interactive-review <run_id>" for run inspection instead.'
        ),
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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    list_handler: Optional[Callable],
    compare_handler: Optional[Callable],
    select_handler: Optional[Callable],
    cancel_handler: Optional[Callable],
) -> None:
    from . import _deprecation_warning

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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    export_handler: Optional[Callable],
    import_handler: Optional[Callable],
    status_handler: Optional[Callable],
    signature_relay_serve_handler: Optional[Callable] = None,
    signature_submit_handler: Optional[Callable] = None,
) -> None:
    """Register sync subcommands."""
    from . import _deprecation_warning

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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    list_handler: Optional[Callable],
    steps_handler: Optional[Callable],
    fork_handler: Optional[Callable],
    resume_handler: Optional[Callable],
) -> None:
    """Register replay subcommands."""
    from . import _deprecation_warning

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
