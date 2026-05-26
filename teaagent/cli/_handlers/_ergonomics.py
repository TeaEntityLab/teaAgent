from __future__ import annotations

import argparse
import subprocess
import sys

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
    print_json([grant.to_dict() for grant in store.list_grants()])
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
    grant = store.deny(args.tool_name)
    print_json(grant.to_dict())
    return 0


def approval_audit_command(args: argparse.Namespace) -> int:
    store = ApprovalPresetStore(args.root)
    print_json(store.audit_tail(args.limit))
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
