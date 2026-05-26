from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Any

from teaagent.cli._handlers._misc import print_json
from teaagent.daily import build_daily_brief
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.ergonomics.daily_journal import write_daily_journal
from teaagent.ergonomics.guidance import collect_workspace_guidance
from teaagent.ergonomics.run_history import list_recall_runs, list_yesterday_runs
from teaagent.ergonomics.status_short import build_status_short
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.policy import parse_permission_mode
from teaagent.recipes.registry import list_recipes, run_recipe
from teaagent.run_store import RunStore


def yesterday_command(args: argparse.Namespace) -> int:
    print_json(list_yesterday_runs(args.root, limit=args.limit))
    return 0


def recall_command(args: argparse.Namespace) -> int:
    print_json(list_recall_runs(args.root, limit=args.limit))
    return 0


def status_short_command(args: argparse.Namespace) -> int:
    defaults = load_workspace_defaults(args.root)
    provider = args.provider or defaults.get('provider')
    if not provider:
        print('teaagent:? provider unset (run teaagent setup)', file=sys.stderr)
        return 1
    line = build_status_short(
        root=args.root,
        provider=provider,
        run_id=args.run_id,
        model=args.model or defaults.get('model'),
        permission_mode=parse_permission_mode(
            args.permission_mode or defaults.get('permission_mode', 'prompt')
        ),
    )
    print(line)
    return 0


def background_list_command(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import BackgroundRunStore

    print_json(BackgroundRunStore(args.root).list())
    return 0


def background_show_command(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import BackgroundRunStore

    try:
        print_json(BackgroundRunStore(args.root).get(args.background_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def session_list_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    rows = []
    for summary in store.list_runs(limit=args.limit):
        row = summary.to_dict()
        row['heartbeat'] = store.heartbeat_for_run(summary.run_id)
        row['pending_approval'] = store.pending_approval_for_run(summary.run_id)
        rows.append(row)
    print_json(rows)
    return 0


def session_show_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(
        {
            'run_id': args.run_id,
            'heartbeat': store.heartbeat_for_run(args.run_id),
            'pending_approval': store.pending_approval_for_run(args.run_id),
            'events': events,
        }
    )
    return 0


def session_resume_command(args: argparse.Namespace) -> int:
    from teaagent.cli._handlers._agent import agent_resume_command

    ns = argparse.Namespace(
        run_id=args.run_id,
        root=args.root,
        provider=args.provider,
        model=args.model,
        fresh_restart=args.fresh_restart,
        approve_call_id=[],
        clarify=False,
        route_model=False,
        max_iterations=10,
        max_tool_calls=10,
        allow_destructive=False,
        hitl_approval=False,
        permission_mode=args.permission_mode,
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
        print_json({'status': 'error', 'message': 'provider required for resume'})
        return 1
    return agent_resume_command(ns)


def recipes_list_command(args: argparse.Namespace) -> int:
    print_json(list_recipes())
    return 0


def recipes_run_command(args: argparse.Namespace) -> int:
    payload = run_recipe(args.name, extra=args.extra or '')
    print_json(payload)
    if args.print_only:
        return 0
    if not args.provider:
        defaults = load_workspace_defaults(args.root)
        args.provider = defaults.get('provider')
    if not args.provider:
        print_json(
            {'status': 'error', 'message': 'provider required to execute recipe'}
        )
        return 1
    from teaagent.cli._handlers._agent import agent_run_task

    run_args = argparse.Namespace(
        provider=args.provider,
        task=payload['task'],
        root=args.root,
        model=args.model,
        route_model=False,
        max_iterations=10,
        max_tool_calls=10,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode=payload['permission_mode'],
        subagent=False,
        max_subagent_depth=1,
        heartbeat=0.0,
        code_analysis=False,
        telemetry_otlp_endpoint=None,
        telemetry_service_name='teaagent',
        telemetry_console=False,
        checkpoint_store=None,
        context_profile=payload['context_profile'],
        _adapter_factory=getattr(args, '_adapter_factory', None),
    )
    return agent_run_task(run_args)


def approval_list_command(args: argparse.Namespace) -> int:
    store = ApprovalPresetStore(args.root)
    if getattr(args, 'grants_only', False):
        print_json([grant.to_dict() for grant in store.list_grants()])
    else:
        print_json(store.list_policy())
    return 0


def approval_check_command(args: argparse.Namespace) -> int:
    import json

    store = ApprovalPresetStore(args.root)
    arguments: dict[str, Any] = {}

    # Parse --arguments-json if provided (highest priority)
    if args.arguments_json:
        try:
            arguments = json.loads(args.arguments_json)
            if not isinstance(arguments, dict):
                print_json(
                    {
                        'status': 'error',
                        'message': '--arguments-json must be a JSON object',
                    }
                )
                return 1
        except json.JSONDecodeError as exc:
            print_json(
                {
                    'status': 'error',
                    'message': f'Invalid JSON in --arguments-json: {exc}',
                }
            )
            return 1
    else:
        # Parse --arg key=value pairs
        for arg_pair in args.arg:
            if '=' not in arg_pair:
                print_json(
                    {
                        'status': 'error',
                        'message': f'Invalid --arg format: {arg_pair} (expected key=value)',
                    }
                )
                return 1
            key, value = arg_pair.split('=', 1)
            arguments[key] = value

        # Fall back to --path and --command for compatibility
        if args.path and 'path' not in arguments:
            arguments['path'] = args.path
        if args.command and 'command' not in arguments:
            arguments['command'] = args.command

    result = store.check(
        args.tool_name,
        permission_mode=args.permission_mode,
        arguments=arguments or None,
    )
    print_json(result)
    return 0


def approval_explain_command(args: argparse.Namespace) -> int:
    import json

    store = ApprovalPresetStore(args.root)
    arguments: dict[str, Any] = {}

    # Parse --arguments-json if provided (highest priority)
    if args.arguments_json:
        try:
            arguments = json.loads(args.arguments_json)
            if not isinstance(arguments, dict):
                print_json(
                    {
                        'status': 'error',
                        'message': '--arguments-json must be a JSON object',
                    }
                )
                return 1
        except json.JSONDecodeError as exc:
            print_json(
                {
                    'status': 'error',
                    'message': f'Invalid JSON in --arguments-json: {exc}',
                }
            )
            return 1
    else:
        # Parse --arg key=value pairs
        for arg_pair in args.arg:
            if '=' not in arg_pair:
                print_json(
                    {
                        'status': 'error',
                        'message': f'Invalid --arg format: {arg_pair} (expected key=value)',
                    }
                )
                return 1
            key, value = arg_pair.split('=', 1)
            arguments[key] = value

        # Fall back to --path and --command for compatibility
        if args.path and 'path' not in arguments:
            arguments['path'] = args.path
        if args.command and 'command' not in arguments:
            arguments['command'] = args.command

    result = store.check(
        args.tool_name,
        permission_mode=args.permission_mode,
        arguments=arguments or None,
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


def approval_revoke_command(args: argparse.Namespace) -> int:
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


def approval_grant_command(args: argparse.Namespace) -> int:
    store = ApprovalPresetStore(args.root)
    grant = store.grant(
        args.tool_name,
        scope=args.scope,
        permission_mode=args.permission_mode,
        path_globs=args.path_glob or None,
        command_prefixes=args.command_prefix or None,
        ttl_hours=args.ttl_hours,
    )
    print_json(grant.to_dict())
    return 0


def approval_deny_command(args: argparse.Namespace) -> int:
    store = ApprovalPresetStore(args.root)
    grant = store.deny(
        args.tool_name,
        path_globs=args.path_glob or None,
        command_prefixes=args.command_prefix or None,
    )
    print_json(grant.to_dict())
    return 0


def approval_audit_command(args: argparse.Namespace) -> int:
    store = ApprovalPresetStore(args.root)
    print_json(store.audit_tail(args.limit))
    return 0


def approval_pending_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    pending_runs = []
    for summary in store.list_runs(limit=args.limit):
        pending = store.pending_approval_for_run(summary.run_id)
        if pending:
            pending_runs.append(
                {
                    'run_id': summary.run_id,
                    'task': summary.task,
                    'status': summary.status,
                    'created_at': summary.created_at,
                    'pending_approval': pending,
                }
            )
    print_json(pending_runs)
    return 0


def approval_approve_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    # Find the run with this pending call_id
    target_run_id = None
    pending_approval = None
    for summary in store.list_runs(limit=100):
        pending = store.pending_approval_for_run(summary.run_id)
        if pending and pending.get('call_id') == args.call_id:
            target_run_id = summary.run_id
            pending_approval = pending
            break

    if not target_run_id:
        print_json(
            {
                'status': 'error',
                'message': f"call_id '{args.call_id}' not found in pending approvals",
            }
        )
        return 1

    # Approve the call
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
            approve_call_id=[args.call_id],
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
        from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

        defaults = load_workspace_defaults(args.root)
        if not ns.provider:
            ns.provider = defaults.get('provider')
        if not ns.provider:
            print_json({'status': 'error', 'message': 'provider required for resume'})
            return 1
        return agent_resume_command(ns)
    else:
        # Record the approval in the audit log
        audit = store.audit_logger(target_run_id)
        audit.record(
            'tool_call_approved',
            target_run_id,
            call_id=args.call_id,
            tool_name=pending_approval.get('tool_name')
            if pending_approval
            else 'unknown',
        )
        # Just approve without resuming
        print_json(
            {
                'status': 'approved',
                'call_id': args.call_id,
                'run_id': target_run_id,
                'note': 'Use --resume to continue the run',
            }
        )
        return 0


def approval_preset_command(args: argparse.Namespace) -> int:
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
    applied = []
    for grant_config in preset['grants']:
        if grant_config['scope'] == 'deny':
            grant = store.deny(
                grant_config['tool_name'],
                path_globs=grant_config.get('path_globs'),
                command_prefixes=grant_config.get('command_prefixes'),
            )
        else:
            grant = store.grant(
                grant_config['tool_name'],
                scope=grant_config['scope'],
                permission_mode=grant_config.get('permission_mode'),
                path_globs=grant_config.get('path_globs'),
                command_prefixes=grant_config.get('command_prefixes'),
            )
        applied.append(grant.to_dict())

    print_json(
        {
            'status': 'applied',
            'preset': preset_name,
            'description': preset['description'],
            'grants_applied': applied,
        }
    )
    return 0


def approval_doctor_command(args: argparse.Namespace) -> int:
    store = ApprovalPresetStore(args.root)
    grants = store.list_grants()

    issues = []
    suggestions = []

    # Check for expired grants
    for grant in grants:
        if grant.expires_at:
            from datetime import datetime, timezone

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

    # Suggest common patterns if missing
    common_tools = {'workspace_write_file', 'bash'}
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

    print_json(
        {
            'status': 'healthy' if not issues else 'issues_found',
            'total_grants': len(grants),
            'issues': issues,
            'suggestions': suggestions,
            'summary': f'{len(issues)} issues, {len(suggestions)} suggestions',
        }
    )
    return 0


def guidance_command(args: argparse.Namespace) -> int:
    print_json(collect_workspace_guidance(args.root))
    return 0


def ci_review_command(args: argparse.Namespace) -> int:
    payload = run_recipe('review-staged')
    if args.diff_only:
        proc = subprocess.run(
            ['git', 'diff', '--staged'],
            cwd=args.root,
            capture_output=True,
            text=True,
            check=False,
        )
        payload['staged_diff'] = proc.stdout[: args.max_bytes]
    print_json(payload)
    if args.print_only:
        return 0
    if not args.provider:
        defaults = load_workspace_defaults(args.root)
        args.provider = defaults.get('provider')
    if not args.provider:
        print_json({'status': 'error', 'message': 'provider required'})
        return 1
    from teaagent.cli._handlers._agent import agent_run_task

    task = payload['task']
    if payload.get('staged_diff'):
        task = f'{task}\n\n```diff\n{payload["staged_diff"]}\n```'
    return agent_run_task(
        argparse.Namespace(
            provider=args.provider,
            task=task,
            root=args.root,
            model=args.model,
            route_model=False,
            max_iterations=8,
            max_tool_calls=8,
            clarify=False,
            allow_destructive=False,
            approve_call_id=[],
            hitl_approval=False,
            permission_mode='read-only',
            subagent=False,
            max_subagent_depth=1,
            heartbeat=0.0,
            code_analysis=False,
            telemetry_otlp_endpoint=None,
            telemetry_service_name='teaagent',
            telemetry_console=False,
            checkpoint_store=None,
            _adapter_factory=getattr(args, '_adapter_factory', None),
        )
    )


def watch_command(args: argparse.Namespace) -> int:
    import time

    interval = max(1.0, float(args.interval))
    while True:
        defaults = load_workspace_defaults(args.root)
        provider = args.provider or defaults.get('provider')
        if provider:
            print(build_status_short(root=args.root, provider=provider), flush=True)
        time.sleep(interval)
    return 0


def daily_journal_command(args: argparse.Namespace) -> int:
    defaults = load_workspace_defaults(args.root)
    provider = args.provider or defaults.get('provider')
    if not provider:
        print_json({'status': 'error', 'message': 'provider required'})
        return 1
    brief = build_daily_brief(
        task=args.task,
        root=args.root,
        provider=provider,
        model=args.model,
        permission_mode=parse_permission_mode(args.permission_mode),
        context_profile=args.context_profile,
    )
    path = write_daily_journal(brief, root=args.root)
    print_json({'ok': True, 'path': str(path)})
    return 0
