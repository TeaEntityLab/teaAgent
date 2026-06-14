from __future__ import annotations

import argparse
from typing import Callable, Optional

from teaagent.llm import available_providers


def _doctor(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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
    config_lint_handler: Optional[Callable] = None,
    config_handler: Optional[Callable] = None,
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

    if config_handler is not None:
        config = subs.add_parser(
            'config',
            help='Print effective config with the source (provenance) of each key.',
        )
        config.add_argument(
            '--root',
            default='.',
            help='Workspace root to inspect for .teaagent/config. Defaults to cwd.',
        )
        config.set_defaults(func=config_handler)

    if config_lint_handler is not None:
        config_lint = subs.add_parser(
            'config-lint',
            help='Warn about unsafe permission, isolation, and cost settings.',
        )
        config_lint.add_argument('--root', default='.', help='Workspace root.')
        config_lint.add_argument(
            '--permission-mode',
            default='prompt',
            help='Permission mode to evaluate (default: prompt).',
        )
        config_lint.add_argument(
            '--allow-destructive',
            action='store_true',
            help='Include allow-destructive posture in lint evaluation.',
        )
        config_lint.add_argument(
            '--subagent-isolation',
            default=None,
            help='Subagent isolation mode override for lint (e.g. shared, worktree).',
        )
        config_lint.set_defaults(func=config_lint_handler)

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
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    handler: Optional[Callable],
) -> None:
    p = subparsers.add_parser('selftest', help='Run harness self-tests (alias).')
    p.add_argument('--security', action='store_true', help='Run security self-test.')
    p.add_argument('--maturity', action='store_true')
    p.add_argument('--root', default='.')
    p.set_defaults(func=handler)


def _audit(
    subparsers: argparse._SubParsersAction,
    list_handler: Callable,
    show_handler: Callable,
    prune_handler: Callable,
    serve_handler: Optional[Callable] = None,
    verify_handler: Optional[Callable] = None,
    export_handler: Optional[Callable] = None,
    decrypt_handler: Optional[Callable] = None,
    tail_handler: Optional[Callable] = None,
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

    tail_cmd = subs.add_parser(
        'tail', help='Show recent run audit events with classification.'
    )
    tail_cmd.add_argument('run_id', help='Run id to tail.')
    tail_cmd.add_argument('--root', default='.', help='Workspace root.')
    tail_cmd.add_argument('--limit', type=int, default=20, help='Number of events.')
    tail_cmd.add_argument(
        '--human',
        action='store_true',
        help='Human-readable output with event classification.',
    )
    if tail_handler is not None:
        tail_cmd.set_defaults(func=tail_handler)

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
        verify_cmd.add_argument(
            '--ci',
            action='store_true',
            help='CI mode: JSON-only output, non-zero exit on failure.',
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

    if decrypt_handler is not None:
        decrypt_cmd = subs.add_parser(
            'decrypt',
            help='Decrypt an L3 audit log file (requires cryptography library).',
        )
        decrypt_cmd.add_argument(
            'audit_path', help='Path to the audit log file to decrypt.'
        )
        decrypt_cmd.add_argument(
            '--key',
            default=None,
            help='Path to encryption key file. If omitted, loads from ~/.teaagent/audit-encryption/<run_id>.enc',
        )
        decrypt_cmd.set_defaults(func=decrypt_handler)


def _env(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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


def _health(subparsers: argparse._SubParsersAction, handler: Callable | None) -> None:
    p = subparsers.add_parser('health', help='Check workspace and harness health.')
    p.add_argument('--root', default='.', help='Workspace root.')
    p.add_argument('--human', action='store_true', help='Human-readable output.')
    p.add_argument('--json', action='store_true', help='Force JSON output.')
    p.set_defaults(func=handler)


def _metrics(subparsers: argparse._SubParsersAction, handler: Callable | None) -> None:
    p = subparsers.add_parser('metrics', help='Show in-process operation metrics.')
    p.add_argument(
        '--structured-logs',
        action='store_true',
        help='Enable structured JSON logging while collecting metrics.',
    )
    p.set_defaults(func=handler)


def _credentials(
    subparsers: argparse._SubParsersAction, handler: Callable | None
) -> None:
    p = subparsers.add_parser('credentials', help='Manage provider credentials.')
    subs = p.add_subparsers(dest='credentials_command', required=True)
    rotate = subs.add_parser('rotate', help='Rotate a provider API key.')
    rotate.add_argument('provider', choices=available_providers())
    rotate.add_argument('--root', default='.', help='Workspace root.')
    rotate.add_argument('--api-key', default=None, help='New API key value.')
    rotate.add_argument(
        '--write-env', action='store_true', help='Write key to .teaagent/env.'
    )
    rotate.add_argument(
        '--write-global',
        action='store_true',
        help='Write key to ~/.teaagent/providers_env.zsh.',
    )
    rotate.add_argument(
        '--dry-run', action='store_true', help='Show plan without writing files.'
    )
    rotate.set_defaults(func=handler)
