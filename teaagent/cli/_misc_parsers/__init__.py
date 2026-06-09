from __future__ import annotations

import argparse
from typing import Callable

from .advanced import (
    _code_ontology,
    _experiment,
    _graphqlite,
    _replay,
    _sync,
    _ultrawork,
    _workspace,
)
from .diagnostics import (
    _audit,
    _credentials,
    _doctor,
    _env,
    _health,
    _metrics,
    _selftest_top_level,
)
from .setup import _clarify, _completion, _configure, _init, _setup
from .surfaces import _surfaces
from .tui_parser import _tui


def _deprecation_warning(args: argparse.Namespace) -> int:
    """Handler for deprecated commands."""
    print('This command is deprecated and not yet implemented.')
    return 1


def register(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
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
        config_lint_handler=handlers.get('doctor_config_lint'),
    )
    _selftest_top_level(subparsers, handlers.get('doctor_selftest'))
    _completion(subparsers, handlers['completion'])
    if handlers.get('surfaces_explain') is not None:
        _surfaces(subparsers, handlers['surfaces_explain'])
    _audit(
        subparsers,
        handlers['audit_list'],
        handlers['audit_show'],
        handlers['audit_prune'],
        serve_handler=handlers.get('audit_serve'),
        verify_handler=handlers.get('audit_verify'),
        export_handler=handlers.get('audit_export'),
        decrypt_handler=handlers.get('audit_decrypt'),
        tail_handler=handlers.get('audit_tail'),
    )
    _env(
        subparsers,
        handlers.get('env_provision'),
        handlers.get('env_verify'),
        handlers.get('env_lock'),
    )
    _health(subparsers, handlers.get('health'))
    _metrics(subparsers, handlers.get('metrics'))
    _credentials(subparsers, handlers.get('credentials_rotate'))
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
