from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from teaagent.cli._handlers._misc import print_json
from teaagent.daily import build_daily_brief
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.ergonomics.daily_journal import write_daily_journal
from teaagent.ergonomics.guidance import collect_workspace_guidance
from teaagent.ergonomics.run_history import list_recall_runs, list_yesterday_runs
from teaagent.ergonomics.status_short import build_status_short
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.policy import PermissionMode, parse_permission_mode
from teaagent.recipes.registry import list_recipes, run_recipe
from teaagent.run_store import RunStore


def _truncate_string(s: str, max_len: int = 40, suffix: str = '...') -> str:
    """Truncate a string to max_len, adding suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix


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


def yesterday_command(args: argparse.Namespace) -> int:
    runs = list_yesterday_runs(args.root, limit=args.limit)
    if sys.stdout.isatty():
        from teaagent.ergonomics.human_output import format_ascii_table

        headers = ['Run ID', 'Task', 'Status', 'Created At']
        keys = ['run_id', 'task', 'status', 'created_at']
        truncated = []
        for r in runs:
            tr = dict(r)
            task = tr.get('task', '')
            tr['task'] = _truncate_string(task, max_len=40)
            truncated.append(tr)
        print(format_ascii_table(headers, truncated, keys))
    else:
        print_json(runs)
    return 0


def recall_command(args: argparse.Namespace) -> int:
    runs = list_recall_runs(args.root, limit=args.limit)
    if sys.stdout.isatty():
        from teaagent.ergonomics.human_output import format_ascii_table

        headers = ['Run ID', 'Task', 'Status', 'Created At']
        keys = ['run_id', 'task', 'status', 'created_at']
        truncated = []
        for r in runs:
            tr = dict(r)
            task = tr.get('task', '')
            tr['task'] = _truncate_string(task, max_len=40)
            truncated.append(tr)
        print(format_ascii_table(headers, truncated, keys))
    else:
        print_json(runs)
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

    runs = BackgroundRunStore(args.root, readonly=True).list()
    if sys.stdout.isatty():
        from teaagent.ergonomics.human_output import format_ascii_table

        headers = ['Background ID', 'PID', 'Label', 'Alive', 'Started At']
        keys = ['background_id', 'pid', 'label', 'alive', 'started_at']
        truncated = []
        for r in runs:
            tr = dict(r)
            tr['background_id'] = tr.get('background_id', '')[:10]
            truncated.append(tr)
        print(format_ascii_table(headers, truncated, keys))
    else:
        print_json(runs)
    return 0


def background_show_command(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import BackgroundRunStore

    try:
        print_json(BackgroundRunStore(args.root, readonly=True).get(args.background_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def session_list_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root, readonly=True)
    rows = []
    for summary in store.list_runs(limit=args.limit):
        row = summary.to_dict()
        row['heartbeat'] = store.heartbeat_for_run(summary.run_id)
        row['pending_approval'] = store.pending_approval_for_run(summary.run_id)
        rows.append(row)
    from teaagent.scratchpad import Scratchpad

    scratchpad = Scratchpad(Path(args.root))
    if scratchpad.exists():
        content = scratchpad.read()
        if content and content.get('last_goal'):
            rows.append({'scratchpad_last_goal': content['last_goal']})
    print_json(rows)
    return 0


def session_show_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root, readonly=True)
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


def _parse_approval_arguments(args: argparse.Namespace) -> dict[str, Any] | None:
    """Parse approval arguments from --arguments-json or --arg key=value pairs.

    Returns:
        Parsed arguments dict, or None if no arguments provided.

    Raises:
        ValueError: If argument parsing fails (error message included).
    """
    import json

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


def approval_why_denied_command(args: argparse.Namespace) -> int:
    """Explain why tool calls were denied for a given run."""
    store = RunStore(Path(args.root), readonly=True)
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
            import json

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
    store = RunStore(args.root, readonly=True)
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
    def _approve() -> int:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = RunStore(args.root)
        approval_store = ApprovalPresetStore(args.root)
        # Find the run with this pending call_id
        target_run_id = None
        pending_approval = None
        for summary in store.list_runs(limit=100):
            pending = store.pending_approval_for_run(summary.run_id)
            if pending and pending.get('call_id') == args.call_id:
                target_run_id = summary.run_id
                pending_approval = pending
                break

        if not target_run_id or pending_approval is None:
            print_json(
                {
                    'status': 'error',
                    'message': f"call_id '{args.call_id}' not found in pending approvals",
                }
            )
            return 1

        pending = pending_approval
        # Persist the approval as a scoped record for exact tool call matching
        approval_store.add_scoped_approval(
            run_id=target_run_id,
            call_id=args.call_id,
            tool_name=pending.get('tool_name', 'unknown'),
            arguments=pending.get('arguments', {}),
        )

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
                print_json(
                    {'status': 'error', 'message': 'provider required for resume'}
                )
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


def approval_doctor_command(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

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
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = RunStore(args.root, readonly=True)

        # Find pending approvals
        pending_runs: list[dict[str, Any]] = []
        for summary in store.list_runs(limit=20):
            pending = store.pending_approval_for_run(summary.run_id)
            if pending:
                pending_runs.append(
                    {
                        'run_id': summary.run_id,
                        'task': summary.task,
                        'status': summary.status,
                        'pending_approval': pending,
                    }
                )

        if not pending_runs:
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

        # Get the first pending approval
        first_pending = pending_runs[0]
        pending_detail: dict[str, Any] = first_pending['pending_approval']
        call_id = str(pending_detail['call_id'])
        tool_name = str(pending_detail['tool_name'])
        arguments = pending_detail.get('arguments', {})
        if not isinstance(arguments, dict):
            arguments = {}

        # Explain why it's pending (lazy-create approval store only when needed)
        from teaagent.policy import PermissionMode

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
        suggestions.append(f'Approve: teaagent approval approve {call_id}')
        suggestions.append(
            f'Approve and resume: teaagent approval approve {call_id} --resume'
        )
        suggestions.append(
            f'Explain: teaagent approval explain {tool_name} --arg path={arguments.get("path", "")}'
        )

        print_json(
            {
                'status': 'pending_found',
                'run_id': first_pending['run_id'],
                'task': first_pending['task'],
                'pending_approval': pending_detail,
                'explanation': {
                    'tool_name': tool_name,
                    'decision': check_result['decision'],
                    'allowed': check_result['allowed'],
                    'matched_grant': check_result['matched_grant'],
                    'evaluated_grants_count': len(check_result['evaluated_grants']),
                },
                'suggestions': suggestions,
                'total_pending': len(pending_runs),
            }
        )
        return 0

    return _wrap_approval_store_errors(_next)


def guidance_command(args: argparse.Namespace) -> int:
    print_json(collect_workspace_guidance(args.root))
    return 0


# ── Permission Mode Decision Guide ────────────────────────────────────────

_PERMISSION_MODE_GUIDE: dict[str, dict[str, str]] = {
    'read-only': {
        'summary': 'Blocks all destructive tools. Safe for exploration and analysis.',
        'when_to_use': 'Code reviews, architecture questions, preflight checks, daily briefs, exploring unfamiliar code.',
        'allows': 'File reads, shell inspect (read-only commands like ls, git log).',
        'blocks': 'File writes (write_file, apply_patch, hash-edit), shell mutation (install, rm, git push).',
        'risk': 'low',
        'rollback': 'not needed (no mutations)',
        'tip': 'Start here for any task that does not require editing files.',
    },
    'workspace-write': {
        'summary': 'Allows file writes but blocks shell mutation. Safe for editing tasks.',
        'when_to_use': 'Patching files, writing docs, updating tests — any task that only needs file I/O.',
        'allows': 'File reads, file writes (write_file, apply_patch, hash-edit), shell inspect.',
        'blocks': 'Shell mutation (install, rm, git push, docker).',
        'risk': 'medium',
        'rollback': 'yes (UndoJournal.restore())',
        'tip': 'Use for editing tasks that do not need to run shell commands with side effects.',
    },
    'prompt': {
        'summary': 'Destructive tools pause for human-in-the-loop approval or require an approval token.',
        'when_to_use': 'Day-to-day autonomous work where you want to approve each destructive action.',
        'allows': 'File reads, file writes (after approval), shell inspect, shell mutate (after approval).',
        'blocks': 'Nothing permanently — every destructive tool can proceed after approval.',
        'risk': 'medium',
        'rollback': 'with approval (UndoJournal.restore())',
        'tip': 'The default mode. Best balance of safety and autonomy for daily use.',
    },
    'allow': {
        'summary': 'Allows all destructive tools for the session. No per-call approval required.',
        'when_to_use': 'Trusted automation, CI/CD pipelines, batch scripts where you have validated the task.',
        'allows': 'File reads, file writes, shell inspect, shell mutate (all without approval).',
        'blocks': 'Nothing.',
        'risk': 'high',
        'rollback': 'yes (UndoJournal.restore())',
        'tip': 'Only use in automated environments where you fully trust the input task.',
    },
    'danger-full-access': {
        'summary': 'Full access with no restrictions. Reserve for trusted automation only.',
        'when_to_use': 'Emergency recovery scripts, fully isolated automation, internal tooling with validated inputs.',
        'allows': 'Everything — file reads/writes, shell inspect/mutate, no approval gates.',
        'blocks': 'Nothing.',
        'risk': 'high',
        'rollback': 'yes (UndoJournal.restore())',
        'tip': 'Identical to "allow" in capability but signals extreme caution. Audit events are tagged for monitoring.',
    },
}


def permission_explain_command(args: argparse.Namespace) -> int:
    """Print the permission mode decision guide."""
    mode_names = [m.value for m in PermissionMode]
    selected = args.mode

    if selected:
        if selected not in mode_names:
            print_json(
                {
                    'error': f"Unknown mode '{selected}'. Choose from: {', '.join(mode_names)}"
                }
            )
            return 1
        modes_to_show = [selected]
    else:
        modes_to_show = mode_names

    result: dict[str, Any] = {'permission_modes': {}}
    for name in modes_to_show:
        result['permission_modes'][name] = _PERMISSION_MODE_GUIDE[name]

    print_json(result)
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
