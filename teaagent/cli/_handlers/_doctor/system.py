from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.llm import available_providers
from teaagent.sandbox import is_git_repository

from .sanitize import print_json


def doctor_all(args: argparse.Namespace) -> int:  # noqa: C901
    """Unified doctor command checking all subsystems with optional auto-repair."""
    checks: dict[str, Any] = {}
    repair_actions: list[str] = []

    # GraphQLite check
    gql_ok, gql_message = args._check_graphqlite(args.database)
    checks['graphqlite'] = {'ok': gql_ok, 'message': gql_message}

    # Providers check
    provider_results = []
    configured_providers = args.provider
    if isinstance(configured_providers, str):
        providers = [configured_providers]
    else:
        providers = configured_providers or available_providers()
    for provider in providers:
        ok, message = args._check_llm(provider)
        provider_results.append({'provider': provider, 'ok': ok, 'message': message})
    checks['providers'] = provider_results

    # Security check
    root = Path(getattr(args, 'root', '.')).resolve()
    security = ApprovalPresetStore(root, readonly=True).check_security_health()
    checks['security'] = security

    # Git sandbox check
    git_repo_ok = is_git_repository(root)
    checks['git_sandbox'] = {
        'ok': git_repo_ok,
        'message': 'Git repository available'
        if git_repo_ok
        else 'Not a git repository',
    }

    # Environment variables check
    env_checks = {
        'WORKERS_AI_BASE_URL': bool(os.environ.get('WORKERS_AI_BASE_URL')),
        'CLOUDFLARE_API_TOKEN': bool(os.environ.get('CLOUDFLARE_API_TOKEN')),
    }
    checks['environment'] = env_checks

    # Overall status
    ok = gql_ok and all(item['ok'] for item in provider_results) and security['ok']

    # Auto-repair logic
    repair = getattr(args, 'repair', False)
    if repair:
        # Fix file permissions
        if not security['ok']:
            try:
                # Fix approval store permissions
                approval_dir = root / '.teaagent' / 'approval'
                if approval_dir.exists():
                    approval_dir.chmod(0o700)
                    for f in approval_dir.iterdir():
                        if f.is_file():
                            f.chmod(0o600)
                    repair_actions.append(
                        'Fixed approval store permissions to 0700/0600'
                    )
                    security = ApprovalPresetStore(
                        root, readonly=True
                    ).check_security_health()
                    checks['security'] = security
            except Exception as exc:
                repair_actions.append(f'Failed to fix permissions: {exc}')

        # Run database migrations if needed
        if not gql_ok:
            try:
                from teaagent.graphqlite_store import (
                    GraphQLiteConfig,
                    GraphQLiteGraphStore,
                )

                GraphQLiteGraphStore(
                    GraphQLiteConfig(database=str(root / '.teaagent' / 'graphqlite.db'))
                )
                # Attempt to initialize/migrate
                repair_actions.append('Attempted GraphQLite database migration')
                # Re-check after migration
                gql_ok, gql_message = args._check_graphqlite(args.database)
                checks['graphqlite'] = {'ok': gql_ok, 'message': gql_message}
            except Exception as exc:
                repair_actions.append(f'Failed to migrate database: {exc}')

    payload = {
        'ok': ok,
        'checks': checks,
        'repair_mode': repair,
        'repair_actions': repair_actions if repair else [],
    }
    print_json(payload)
    return 0 if ok else 1


def doctor_selftest_command(args: argparse.Namespace) -> int:
    from teaagent.selftest import run_security_selftest

    root = Path(getattr(args, 'root', '.')).resolve()
    if getattr(args, 'maturity', False):
        print_json(
            {
                'ok': True,
                'message': 'Maturity selftest is documentation-only; see docs/maturity-matrix.md',
            }
        )
        return 0
    payload = run_security_selftest(root)
    print_json(payload)
    return 0 if payload['ok'] else 1


def doctor_migration_command(args: argparse.Namespace) -> int:
    from teaagent.schema_migration import SQLiteMigrationStore

    store_path = getattr(args, 'store', None)
    if not store_path:
        print_json(
            {'ok': False, 'error': '--store <path> is required for migration check'}
        )
        return 1
    try:
        store = SQLiteMigrationStore(store_path)
        status = store.status([])
        print_json({'ok': True, 'store': store_path, 'status': status})
        return 0
    except Exception as exc:
        print_json({'ok': False, 'error': str(exc)})
        return 1


def doctor_review_institution(args: argparse.Namespace) -> int:
    """Review institution health: mode, pending actions, audit-chain status.

    Per review-system.md §11: reports current mode (A/B/C), pending action
    register items, and audit-chain health summary.
    """
    root = Path(getattr(args, 'root', '.')).resolve()
    action_register = root / 'docs' / 'retrospective' / '06-action-register.md'

    pending_actions: list[dict[str, str]] = []
    if action_register.is_file():
        import re

        content = action_register.read_text(encoding='utf-8')
        for match in re.finditer(
            r'\| ([SGUA]-P[0-2]-[0-9]) \|[^|]*\|[^|]*\|[^|]*\|[^|]*\| (⬜|🟡) \|',
            content,
        ):
            pending_actions.append({'id': match.group(1), 'status': match.group(2)})

    mode = os.environ.get('TEAAGENT_REVIEW_INSTITUTION', 'solo')

    audit_health: dict[str, Any] = {'available': False}
    try:
        from teaagent.audit_chain import verify_audit_chain

        audit_dir = root / '.teaagent' / 'audit'
        if audit_dir.is_dir():
            logs = sorted(audit_dir.glob('*.jsonl'))
            if logs:
                result = verify_audit_chain(logs[-1])
                audit_health = {
                    'available': True,
                    'ok': result.valid,
                    'total_events': result.event_count,
                    'total_hash_mismatches': result.total_hash_mismatches,
                    'total_prev_hash_mismatches': result.total_prev_hash_mismatches,
                }
    except Exception as exc:
        audit_health = {'available': False, 'error': str(exc)}

    payload = {
        'ok': True,
        'mode': mode,
        'pending_action_count': len(pending_actions),
        'pending_actions': pending_actions[:20],
        'audit_health': audit_health,
    }
    print_json(payload)
    return 0


def doctor_git_sandbox(args: argparse.Namespace) -> int:
    """Check for orphaned git sandbox branches."""
    from teaagent.sandbox import (
        find_orphaned_sandbox_branches,
        is_git_repository,
        prune_sandbox_branch,
    )

    root = Path(getattr(args, 'root', '.')).resolve()
    prune = getattr(args, 'prune', False)

    if not is_git_repository(root):
        payload = {
            'ok': True,
            'mode': 'checklist',
            'root': str(root),
            'is_git_repo': False,
            'message': 'Not a git repository',
            'orphaned_branches': [],
        }
        print_json(payload)
        return 0

    orphaned = find_orphaned_sandbox_branches(root)

    if prune and orphaned:
        pruned: list[str] = []
        failed: list[dict[str, str]] = []
        for branch_info in orphaned:
            branch_name = branch_info['branch_name']
            if prune_sandbox_branch(root, branch_name):
                pruned.append(branch_name)
            else:
                failed.append({'branch': branch_name, 'error': 'deletion_failed'})

        payload = {
            'ok': len(failed) == 0,
            'mode': 'prune',
            'root': str(root),
            'orphaned_branches': orphaned,
            'pruned': pruned,
            'failed': failed,
            'message': f'Pruned {len(pruned)} branches'
            if pruned
            else 'No branches pruned',
        }
        print_json(payload)
        return 0 if len(failed) == 0 else 1
    else:
        payload = {
            'ok': len(orphaned) == 0,
            'mode': 'check',
            'root': str(root),
            'orphaned_branches': orphaned,
            'message': f'Found {len(orphaned)} orphaned branches'
            if orphaned
            else 'No orphaned branches',
            'next_steps': [
                'teaagent doctor git-sandbox --prune',
            ]
            if orphaned
            else [],
        }
        print_json(payload)
        return 0 if len(orphaned) == 0 else 1
