"""``teaagent approval doctor`` command.

Extracted from ``approval.py`` (A-P2-2 god-module split). Re-exported from
``approval.py`` so the public surface is unchanged.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from teaagent.ergonomics.approval_store import ApprovalPresetStore

from .approval import print_json


def approval_doctor_command(args: argparse.Namespace) -> int:  # noqa: C901
    readonly = not (
        getattr(args, 'repair_store', False)
        or getattr(args, 'force_reset_store', False)
        or getattr(args, 'prune_expired', False)
        or getattr(args, 'fix_duplicates', False)
        or getattr(args, 'fix_security', False)
    )
    store = ApprovalPresetStore(args.root, readonly=readonly)

    # Handle explicit store repair if requested
    if getattr(args, 'repair_store', False) or getattr(
        args, 'force_reset_store', False
    ):
        try:
            reset_healthy = getattr(args, 'force_reset_store', False)
            repair_result = store.repair_store(reset_healthy=reset_healthy)
            if repair_result['status'] == 'noop':
                print_json(
                    {
                        'status': 'noop',
                        'message': repair_result['message'],
                    }
                )
                return 0
            action = 'reset' if repair_result['status'] == 'reset' else 'repaired'
            actions_taken = [f'Store {action}. Backup: {repair_result["backup_path"]}']
            print_json(
                {
                    'status': repair_result['status'],
                    'backup_path': repair_result['backup_path'],
                    'actions_taken': actions_taken,
                }
            )
            return 0
        except IOError as exc:
            print_json(
                {
                    'status': 'error',
                    'message': str(exc),
                }
            )
            return 1

    # Run security health check first (before grant analysis) to detect corrupt files
    fix_security = getattr(args, 'fix_security', False)
    try:
        security = store.check_security_health(fix_permissions=fix_security)
    except IOError as exc:
        # Store is corrupt, suggest repair
        print_json(
            {
                'status': 'issues_found',
                'issues': [str(exc)],
                'suggested_command': 'teaagent approval doctor --repair-store',
            }
        )
        return 1

    # Now try to load grants (may fail if corrupt)
    try:
        grants = store.list_grants()
    except IOError as exc:
        print_json(
            {
                'status': 'issues_found',
                'issues': [str(exc)],
                'suggested_command': 'teaagent approval doctor --repair-store',
            }
        )
        return 1

    issues = []
    suggestions = []
    actions_taken = []

    # Check for expired grants
    expired_grant_ids = []
    for grant in grants:
        if grant.expires_at:
            try:
                expires = datetime.fromisoformat(grant.expires_at)
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= expires:
                    issues.append(
                        f'Grant {grant.grant_id} ({grant.tool_name}) expired at {grant.expires_at}'
                    )
                    expired_grant_ids.append(grant.grant_id)
            except ValueError:
                issues.append(
                    f'Grant {grant.grant_id} ({grant.tool_name}) has invalid expiry: {grant.expires_at}'
                )

    # Prune expired grants if requested
    if args.prune_expired and expired_grant_ids:
        for grant_id in expired_grant_ids:
            if store.revoke(grant_id):
                actions_taken.append(f'Revoked expired grant {grant_id}')
        # Refresh grants after pruning
        grants = store.list_grants()
        # Recalculate issues after pruning
        issues = []
        for grant in grants:
            if grant.expires_at:
                try:
                    expires = datetime.fromisoformat(grant.expires_at)
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) >= expires:
                        issues.append(
                            f'Grant {grant.grant_id} ({grant.tool_name}) expired at {grant.expires_at}'
                        )
                except ValueError:
                    issues.append(
                        f'Grant {grant.grant_id} ({grant.tool_name}) has invalid expiry: {grant.expires_at}'
                    )

    # Check for conflicting rules (deny + allow for same tool)
    tool_scopes: dict[str, list[str]] = {}
    for grant in grants:
        if grant.tool_name not in tool_scopes:
            tool_scopes[grant.tool_name] = []
        tool_scopes[grant.tool_name].append(grant.scope)

    for tool_name, scopes in tool_scopes.items():
        if 'deny' in scopes and ('session' in scopes or 'always' in scopes):
            issues.append(
                f'Tool {tool_name} has both deny and allow grants - deny takes precedence'
            )

    # Check for duplicate grants
    grant_signatures = {}
    duplicate_grant_ids = []
    for grant in grants:
        signature = (
            grant.tool_name,
            grant.scope,
            grant.permission_mode,
            tuple(sorted(grant.path_globs)),
            tuple(sorted(grant.command_prefixes)),
        )
        if signature in grant_signatures:
            duplicate_grant_ids.append(grant.grant_id)
        else:
            grant_signatures[signature] = grant.grant_id

    # Fix duplicates if requested
    if args.fix_duplicates and duplicate_grant_ids:
        for grant_id in duplicate_grant_ids:
            if store.revoke(grant_id):
                actions_taken.append(f'Revoked duplicate grant {grant_id}')
        # Refresh grants after removing duplicates
        grants = store.list_grants()
        # Recalculate duplicate check
        grant_signatures = {}
        duplicate_grant_ids = []
        for grant in grants:
            signature = (
                grant.tool_name,
                grant.scope,
                grant.permission_mode,
                tuple(sorted(grant.path_globs)),
                tuple(sorted(grant.command_prefixes)),
            )
            if signature in grant_signatures:
                duplicate_grant_ids.append(grant.grant_id)
            else:
                grant_signatures[signature] = grant.grant_id

    # Only add duplicate issue if duplicates still exist (either not fixed or fix failed)
    if duplicate_grant_ids:
        issues.append(
            f'Found {len(duplicate_grant_ids)} duplicate grants that can be removed'
        )

    # Check for expired or consumed scoped approvals
    all_scoped = store.list_all_scoped_approvals()
    expired_or_consumed = [
        r for r in all_scoped if r['status'] in {'expired', 'consumed'}
    ]
    if expired_or_consumed:
        issues.append(
            f'Found {len(expired_or_consumed)} expired or consumed scoped approvals that can be pruned'
        )

    # Prune expired or consumed scoped approvals if requested
    if args.prune_expired and expired_or_consumed:
        pruned_scoped = store.prune_scoped_approvals()
        if pruned_scoped > 0:
            actions_taken.append(
                f'Pruned {pruned_scoped} expired or consumed scoped approvals'
            )
            # Recalculate
            all_scoped = store.list_all_scoped_approvals()
            expired_or_consumed = [
                r for r in all_scoped if r['status'] in {'expired', 'consumed'}
            ]
            issues = [
                iss
                for iss in issues
                if not (
                    iss.startswith('Found ')
                    and 'scoped approvals that can be pruned' in iss
                )
            ]

    # Check for legacy bare approved call IDs
    legacy_ids = store.list_approved_call_ids()
    if legacy_ids:
        issues.append(f'Found {len(legacy_ids)} legacy bare approved_call_ids residue')

    # Clear legacy bare approved call IDs if requested
    if args.fix_duplicates and legacy_ids:
        cleared_legacy = store.clear_legacy_approved_call_ids()
        if cleared_legacy > 0:
            actions_taken.append(
                f'Cleared {cleared_legacy} legacy bare approved_call_ids residue'
            )
            # Remove legacy issues
            issues = [
                iss
                for iss in issues
                if not (
                    iss.startswith('Found ')
                    and 'legacy bare approved_call_ids residue' in iss
                )
            ]

    # Suggest pruning if unconsumed active scoped approvals > 50
    active_scoped = [r for r in all_scoped if r['status'] == 'active']
    if len(active_scoped) > 50:
        suggestions.append(
            f'Found {len(active_scoped)} active unconsumed scoped approvals. Consider pruning them if associated runs are finished.'
        )

    # Suggest common patterns if missing
    common_tools = {
        'workspace_write_file',
        'workspace_run_shell_mutate',
        'workspace_apply_patch',
    }
    existing_tools = {grant.tool_name for grant in grants}
    for tool in common_tools - existing_tools:
        suggestions.append(
            f'Consider adding grants for {tool} (common destructive tool)'
        )

    # Check for overly broad rules
    for grant in grants:
        if (
            grant.scope == 'always'
            and not grant.path_globs
            and not grant.command_prefixes
        ):
            suggestions.append(
                f'Grant {grant.grant_id} ({grant.tool_name}) is always allowed without restrictions - consider scoping with path_globs or command_prefixes'
            )

    fix_security = getattr(args, 'fix_security', False)
    security = store.check_security_health(fix_permissions=fix_security)
    if not security['ok']:
        issues.extend(
            c['message']
            for c in security['checks']
            if not c['ok'] and c['severity'] == 'error'
        )
    if fix_security:
        if security['fixed_count'] > 0:
            actions_taken.append(
                f'Security permissions fixed: {security["fixed_count"]} items'
            )
        if security['verified_count'] > 0:
            actions_taken.append(
                f'Security permissions verified: {security["verified_count"]} items'
            )
    status = 'healthy' if not issues else 'issues_found'
    print_json(
        {
            'status': status,
            'total_grants': len(grants),
            'issues': issues,
            'suggestions': suggestions,
            'actions_taken': actions_taken,
            'security': security,
            'summary': f'{len(issues)} issues, {len(suggestions)} suggestions',
        }
    )
    # Return non-zero exit code if there are issues (for CI usage)
    return 1 if issues else 0
