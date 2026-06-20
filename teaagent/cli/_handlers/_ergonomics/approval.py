from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from teaagent.approval_selectors import (
    collect_pending_approval_views,
    format_pending_approvals,
    resolve_selector,
)
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.integration.approval_parity import (
    build_approval_granted_payload,
    build_pending_approvals_snapshot,
    grant_pending_approval,
)
from teaagent.types import PermissionMode


class _PrintJsonProxy:
    """Print JSON via the parent package to support test patching of
    ``teaagent.cli._handlers._ergonomics.print_json``.
    """

    def __call__(self, value: Any) -> None:
        import sys as _sys

        mod = _sys.modules.get('teaagent.cli._handlers._ergonomics')
        if mod is not None and hasattr(mod, 'print_json'):
            mod.print_json(value)
            return
        from teaagent.cli._handlers._misc import print_json as _fallback

        _fallback(value)


print_json = _PrintJsonProxy()


def _wrap_approval_store_errors(func: Callable[[], int]) -> int:
    """Unified error boundary for approval store operations.

    Catches IOError from corrupt approvals.json and returns a helpful JSON response
    suggesting the repair command instead of crashing with a raw exception.
    """
    try:
        return func()
    except IOError as exc:
        print_json(
            {
                'status': 'issues_found',
                'issues': [str(exc)],
                'suggested_command': 'teaagent approval doctor --repair-store',
            }
        )
        return 1


def _parse_approval_arguments(args: argparse.Namespace) -> dict[str, Any] | None:
    """Parse approval arguments from --arguments-json or --arg key=value pairs.

    Returns:
        Parsed arguments dict, or None if no arguments provided.

    Raises:
        ValueError: If argument parsing fails (error message included).
    """
    arguments: dict[str, Any] = {}

    # Parse --arguments-json if provided (highest priority)
    if args.arguments_json:
        try:
            arguments = json.loads(args.arguments_json)
            if not isinstance(arguments, dict):
                raise ValueError('--arguments-json must be a JSON object')
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid JSON in --arguments-json: {exc}') from exc
    else:
        # Parse --arg key=value pairs
        for arg_pair in args.arg:
            if '=' not in arg_pair:
                raise ValueError(
                    f'Invalid --arg format: {arg_pair} (expected key=value)'
                )
            key, value = arg_pair.split('=', 1)
            arguments[key] = value

        # Fall back to --path and --command for compatibility
        if args.path and 'path' not in arguments:
            arguments['path'] = args.path
        if args.command and 'command' not in arguments:
            arguments['command'] = args.command

    return arguments or None


def _build_explanation_summary(check_result: dict[str, Any]) -> str:
    """Build human-readable explanation of why a tool call was allowed/denied."""
    decision = check_result['decision']
    evaluated = check_result['evaluated_grants']
    matched = check_result['matched_grant']

    if decision == 'deny':
        if matched:
            return f'Denied by matching deny grant {matched["grant_id"]}'
        return 'Denied by permission mode or no matching allow grant'
    if decision == 'allow':
        if matched:
            return f'Allowed by matching {matched["scope"]} grant {matched["grant_id"]}'
        return 'Allowed by permission mode'
    if decision == 'prompt':
        # Find reasons why grants didn't match
        reasons = []
        for grant in evaluated:
            if not grant['matched'] and grant.get('reason'):
                reasons.append(
                    f'Grant {grant["grant_id"]} ({grant["scope"]}): {grant["reason"]}'
                )
        if reasons:
            return f'Prompt required. No matching grant. Reasons: {"; ".join(reasons)}'
        return 'Prompt required. No matching grant found'
    return f'Unknown decision: {decision}'


_DENIAL_REASON_DESCRIPTIONS: dict[str, str] = {
    'read_only_mode': 'Blocked by read-only permission mode — all destructive tools are disabled.',
    'workspace_write_mode': 'Blocked by workspace-write permission mode — shell mutation tools require prompt/allow mode.',
    'file_policy_denied': 'Blocked by file policy rules in policy.yaml.',
    'plan_contract_denied': 'Blocked by plan-before-write enforcement — target is not in the approved plan.',
    'jit_user_denied': 'Denied by user via the JIT approval prompt.',
    'jit_no_approval': 'No explicit approval received — tool call requires approval.',
    'multisig_no_quorum': 'Blocked by multi-signature quorum — not enough peer approvals.',
    'auto_mode_blocked': 'Blocked by auto-mode tool restrictions.',
    'missing_state': 'Blocked — no matching approval state found.',
}


def approval_list_command(args: argparse.Namespace) -> int:
    def _list() -> int:
        store = ApprovalPresetStore(args.root, readonly=True)
        if getattr(args, 'scoped', False):
            print_json(store.list_all_scoped_approvals())
        elif getattr(args, 'grants_only', False):
            print_json([grant.to_dict() for grant in store.list_grants()])
        else:
            print_json(store.list_policy())
        return 0

    return _wrap_approval_store_errors(_list)


def approval_check_command(args: argparse.Namespace) -> int:
    def _check() -> int:
        store = ApprovalPresetStore(args.root, readonly=True)

        try:
            arguments = _parse_approval_arguments(args)
        except ValueError as exc:
            print_json(
                {
                    'status': 'error',
                    'message': str(exc),
                }
            )
            return 1

        result = store.check(
            args.tool_name,
            permission_mode=args.permission_mode,
            arguments=arguments,
        )
        print_json(result)
        return 0

    return _wrap_approval_store_errors(_check)


def approval_explain_command(args: argparse.Namespace) -> int:
    def _explain() -> int:
        store = ApprovalPresetStore(args.root, readonly=True)

        try:
            arguments = _parse_approval_arguments(args)
        except ValueError as exc:
            print_json(
                {
                    'status': 'error',
                    'message': str(exc),
                }
            )
            return 1

        result = store.check(
            args.tool_name,
            permission_mode=args.permission_mode,
            arguments=arguments,
            include_inactive=True,
        )
        # Add explanation summary
        explanation = {
            'tool_name': args.tool_name,
            'permission_mode': args.permission_mode,
            'arguments': arguments,
            'decision': result['decision'],
            'allowed': result['allowed'],
            'policy_order': result['policy_order'],
            'evaluated_grants': result['evaluated_grants'],
            'matched_grant': result['matched_grant'],
            'summary': _build_explanation_summary(result),
        }
        print_json(explanation)
        return 0

    return _wrap_approval_store_errors(_explain)


def approval_why_denied_command(args: argparse.Namespace) -> int:
    """Explain why tool calls were denied for a given run."""
    store = AgentExecutionFactory(Path(args.root)).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError:
        print_json(
            {
                'status': 'error',
                'message': f"run '{args.run_id}' not found",
            }
        )
        return 1

    denial_events = [
        e
        for e in events
        if isinstance(e, dict)
        and e.get('event_type') in ('tool_call_denied', 'tool_call_blocked')
    ]

    if args.call_id:
        denial_events = [
            e
            for e in denial_events
            if e.get('payload', {}).get('call_id') == args.call_id
        ]

    if not denial_events:
        print(f'No denials found for run {args.run_id}')
        return 0

    for event in denial_events:
        payload = event.get('payload', {})
        reason_code = payload.get('reason_code', 'unknown')
        description = _DENIAL_REASON_DESCRIPTIONS.get(
            reason_code, 'Unknown denial reason.'
        )
        tool_name = payload.get('tool_name', 'unknown')
        call_id = payload.get('call_id', 'unknown')
        created_at = event.get('created_at', 'unknown')

        print(
            f'--- Denial at {created_at} ---\n'
            f'  Tool:     {tool_name}\n'
            f'  Call ID:  {call_id}\n'
            f'  Reason:   {reason_code}\n'
            f'  Detail:   {description}'
        )

        if args.verbose:
            print(f'  Full payload:\n    {json.dumps(payload, indent=4)}')
        print()

    return 0


def approval_revoke_command(args: argparse.Namespace) -> int:
    def _revoke() -> int:
        store = ApprovalPresetStore(args.root)
        revoked = store.revoke(args.grant_id)
        if not revoked:
            print_json(
                {
                    'status': 'error',
                    'message': f"grant '{args.grant_id}' not found",
                }
            )
            return 1
        print_json({'status': 'revoked', 'grant_id': args.grant_id})
        return 0

    return _wrap_approval_store_errors(_revoke)


def approval_grant_command(args: argparse.Namespace) -> int:
    def _grant() -> int:
        store = ApprovalPresetStore(args.root)
        # Session-scope: None means no path restriction (temporary grant).
        # Other scopes require explicit patterns to prevent implicit global grants.
        if args.scope == 'session':
            path_globs = args.path_glob or None
            command_prefixes = args.command_prefix or None
        else:
            # For non-session scopes, require explicit patterns
            if not args.path_glob and not args.command_prefix:
                print(
                    f'[error] scope={args.scope} requires at least one path_glob or command_prefix',
                    file=sys.stderr,
                )
                return 1
            path_globs = args.path_glob or None
            command_prefixes = args.command_prefix or None
        grant = store.grant(
            args.tool_name,
            scope=args.scope,
            permission_mode=args.permission_mode,
            path_globs=path_globs,
            command_prefixes=command_prefixes,
            ttl_hours=args.ttl_hours,
        )
        print_json(grant.to_dict())
        return 0

    return _wrap_approval_store_errors(_grant)


def approval_deny_command(args: argparse.Namespace) -> int:
    def _deny() -> int:
        store = ApprovalPresetStore(args.root)
        grant = store.deny(
            args.tool_name,
            path_globs=args.path_glob or None,
            command_prefixes=args.command_prefix or None,
        )
        print_json(grant.to_dict())
        return 0

    return _wrap_approval_store_errors(_deny)


def approval_audit_command(args: argparse.Namespace) -> int:
    def _audit() -> int:
        store = ApprovalPresetStore(args.root)
        events = store.audit_tail(args.limit)
        if getattr(args, 'scoped', False):
            scoped_actions = {
                'scoped_approval',
                'consume_scoped_approval',
                'consume_once',
                'prune_scoped_approvals',
                'clear_legacy_approved_call_ids',
            }
            events = [e for e in events if e.get('action') in scoped_actions]
        print_json(events)
        return 0

    return _wrap_approval_store_errors(_audit)


def approval_pending_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    if getattr(args, 'human', False):
        views = collect_pending_approval_views(store, limit=args.limit)
        print(format_pending_approvals(views))
        return 0
    print_json(build_pending_approvals_snapshot(store, limit=args.limit))
    return 0


def approval_approve_command(args: argparse.Namespace) -> int:  # noqa: C901
    def _approve() -> int:  # noqa: C901
        store = AgentExecutionFactory(args.root).create_run_store()
        call_id = args.call_id
        if getattr(args, 'selector', None) is not None:
            views = collect_pending_approval_views(store, limit=100)
            selected = resolve_selector(views, args.selector)
            if selected is None:
                print_json(
                    {
                        'status': 'error',
                        'message': f"selector '{args.selector}' not found in pending approvals",
                    }
                )
                return 1
            call_id = selected.call_id

        if not call_id:
            print_json(
                {
                    'status': 'error',
                    'message': 'Provide call_id or --selector N',
                }
            )
            return 1

        grant = grant_pending_approval(args.root, call_id, limit=100)
        if grant is None:
            print_json(
                {
                    'status': 'error',
                    'message': f"call_id '{call_id}' not found in pending approvals",
                }
            )
            return 1
        target_run_id = str(grant['run_id'])
        pending_approval = store.pending_approval_for_run(target_run_id)

        from teaagent.cli._handlers._agent import agent_resume_command

        if args.resume:
            # Load the original run to get its permission mode
            original_permission_mode = 'prompt'
            try:
                for event in store.show_run(target_run_id):
                    if event.get('event_type') != 'run_started':
                        continue
                    payload = event.get('payload') or {}
                    mode = payload.get('permission_mode')
                    if isinstance(mode, str) and mode:
                        original_permission_mode = mode
                    break
            except FileNotFoundError:
                original_permission_mode = 'prompt'

            # Resume the run with the call_id approved
            ns = argparse.Namespace(
                run_id=target_run_id,
                root=args.root,
                provider=None,
                model=None,
                fresh_restart=False,
                approve_call_id=[call_id],
                clarify=False,
                route_model=False,
                max_iterations=10,
                max_tool_calls=10,
                allow_destructive=False,
                hitl_approval=False,
                permission_mode=original_permission_mode,
                subagent=False,
                max_subagent_depth=1,
                heartbeat=0.0,
                code_analysis=False,
                telemetry_otlp_endpoint=None,
                telemetry_service_name='teaagent',
                telemetry_console=False,
                checkpoint_store=None,
                auto_compact=None,
                _adapter_factory=getattr(args, '_adapter_factory', None),
            )
            defaults = load_workspace_defaults(args.root)
            if not ns.provider:
                ns.provider = defaults.get('provider')
            if not ns.provider:
                print_json(
                    {'status': 'error', 'message': 'provider required for resume'}
                )
                return 1
            return agent_resume_command(ns)
        else:
            audit = store.audit_logger(target_run_id)
            audit.record(
                'tool_call_approved',
                target_run_id,
                call_id=call_id,
                tool_name=pending_approval.get('tool_name')
                if pending_approval
                else grant.get('tool_name', 'unknown'),
            )
            print_json(build_approval_granted_payload(grant))
            return 0

    return _wrap_approval_store_errors(_approve)


def approval_preset_command(args: argparse.Namespace) -> int:
    def _preset() -> int:
        store = ApprovalPresetStore(args.root)
        preset_name = args.name

        # Define preset templates
        presets: dict[str, dict[str, Any]] = {
            'dev-safe': {
                'description': 'Allow workspace writes, pytest, git diff/status; deny secrets/** and deploy commands',
                'grants': [
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'session',
                        'path_globs': ['src/**', 'tests/**', '*.py', '*.md', '*.txt'],
                        'permission_mode': 'workspace-write',
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'session',
                        'command_prefixes': ['pytest ', 'git diff', 'git status'],
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'deny',
                        'command_prefixes': ['deploy', 'prod', 'production'],
                    },
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'deny',
                        'path_globs': ['secrets/**', '.env*', '*.key', '*.pem'],
                    },
                ],
            },
            'ci-safe': {
                'description': 'Read-only mode for CI environments',
                'grants': [
                    {
                        'tool_name': 'workspace_read_file',
                        'scope': 'always',
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'session',
                        'command_prefixes': ['git diff', 'git status', 'cat ', 'ls '],
                    },
                ],
            },
            'strict': {
                'description': 'Deny all destructive tools, require explicit approval',
                'grants': [
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'deny',
                    },
                    {
                        'tool_name': 'workspace_run_shell_mutate',
                        'scope': 'deny',
                    },
                ],
            },
        }

        if preset_name not in presets:
            print_json({'status': 'error', 'message': f'Unknown preset: {preset_name}'})
            return 1

        preset = presets[preset_name]

        # Check for duplicate grants to avoid bloat
        existing_grants = store.list_grants()
        existing_signatures = {
            (
                g.tool_name,
                g.scope,
                g.permission_mode,
                tuple(sorted(g.path_globs)),
                tuple(sorted(g.command_prefixes)),
            )
            for g in existing_grants
        }

        applied = []
        skipped = []
        for grant_config in preset['grants']:
            # Compute signature for deduplication
            signature = (
                grant_config['tool_name'],
                grant_config['scope'],
                grant_config.get('permission_mode'),
                tuple(sorted(grant_config.get('path_globs', []))),
                tuple(sorted(grant_config.get('command_prefixes', []))),
            )
            if signature in existing_signatures:
                skipped.append(grant_config)
                continue

            # Deny scope requires explicit patterns to prevent implicit global denials
            if grant_config['scope'] == 'deny':
                path_globs = grant_config.get('path_globs') or None
                command_prefixes = grant_config.get('command_prefixes') or None
                if not path_globs and not command_prefixes:
                    print(
                        f'[warning] Skipping deny grant for {grant_config["tool_name"]}: '
                        f'deny scope requires at least one path_glob or command_prefix',
                        file=sys.stderr,
                    )
                    skipped.append(grant_config)
                    continue
                grant = store.deny(
                    grant_config['tool_name'],
                    path_globs=path_globs,
                    command_prefixes=command_prefixes,
                )
            else:
                # For non-deny scopes, session allows None, others require patterns
                if grant_config['scope'] == 'session':
                    path_globs = grant_config.get('path_globs') or None
                    command_prefixes = grant_config.get('command_prefixes') or None
                else:
                    path_globs = grant_config.get('path_globs') or None
                    command_prefixes = grant_config.get('command_prefixes') or None
                    if not path_globs and not command_prefixes:
                        print(
                            f'[warning] Skipping grant for {grant_config["tool_name"]}: '
                            f'scope={grant_config["scope"]} requires at least one path_glob or command_prefix',
                            file=sys.stderr,
                        )
                        skipped.append(grant_config)
                        continue
                grant = store.grant(
                    grant_config['tool_name'],
                    scope=grant_config['scope'],
                    permission_mode=grant_config.get('permission_mode'),
                    path_globs=path_globs,
                    command_prefixes=command_prefixes,
                )
            applied.append(grant.to_dict())
            existing_signatures.add(signature)

        print_json(
            {
                'status': 'applied',
                'preset': preset_name,
                'description': preset['description'],
                'grants_applied': applied,
                'grants_skipped': skipped,
            }
        )
        return 0

    return _wrap_approval_store_errors(_preset)


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


def approval_next_command(args: argparse.Namespace) -> int:
    def _next() -> int:
        store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
        views = collect_pending_approval_views(store, limit=20)

        if not views:
            if getattr(args, 'human', False):
                print('No pending approvals found.')
                return 0
            print_json(
                {
                    'status': 'no_pending',
                    'message': 'No pending approvals found',
                    'suggestions': [
                        'Use "teaagent run" to start a new task',
                        'Use "teaagent approval list" to view current grants',
                    ],
                }
            )
            return 0

        first_view = views[0]
        if getattr(args, 'human', False):
            print(format_pending_approvals(views))
            return 0

        pending = store.pending_approval_for_run(first_view.run_id) or {}
        pending_detail = dict(pending)
        tool_name = first_view.tool_name
        arguments = pending_detail.get('arguments', {})
        if not isinstance(arguments, dict):
            arguments = {}

        # Explain why it's pending (lazy-create approval store only when needed)
        permission_mode = PermissionMode.PROMPT.value
        approval_store = ApprovalPresetStore(args.root, readonly=True)
        check_result = approval_store.check(
            tool_name,
            permission_mode=permission_mode,
            arguments=arguments,
            include_inactive=True,
        )

        # Build suggestions
        suggestions = []
        matched_grant = check_result.get('matched_grant', {})
        if matched_grant:
            scope = matched_grant.get('scope', 'unknown')
            suggestions.append(
                f'This tool call matches a {scope} grant but may need explicit approval'
            )
        else:
            suggestions.append(
                'No matching grant found - consider adding a preset or explicit approval'
            )
            suggestions.append('Try: teaagent approval preset dev-safe')
        suggestions.append(
            f'Approve: teaagent approval approve --selector {first_view.selector}'
        )
        suggestions.append(
            f'Approve and resume: teaagent approval approve --selector {first_view.selector} --resume'
        )
        suggestions.append('Human list: teaagent approval pending --human')
        suggestions.append(
            f'Explain: teaagent approval explain {tool_name} --arg path={arguments.get("path", "")}'
        )

        print_json(
            {
                'status': 'pending_found',
                'selector': first_view.selector,
                'run_id': first_view.run_id,
                'task': first_view.task,
                'pending_approval': pending_detail,
                'path_summary': first_view.path_summary,
                'risk_class': first_view.risk_class,
                'expires_at': first_view.expires_at,
                'explanation': {
                    'tool_name': tool_name,
                    'decision': check_result['decision'],
                    'allowed': check_result['allowed'],
                    'matched_grant': check_result['matched_grant'],
                    'evaluated_grants_count': len(check_result['evaluated_grants']),
                },
                'suggestions': suggestions,
                'total_pending': len(views),
            }
        )
        return 0

    return _wrap_approval_store_errors(_next)
