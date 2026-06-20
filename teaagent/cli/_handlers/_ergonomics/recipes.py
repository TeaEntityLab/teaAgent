from __future__ import annotations

import argparse
import subprocess
import time

from teaagent.approval import parse_permission_mode
from teaagent.cli._handlers._misc import print_json
from teaagent.daily import build_daily_brief
from teaagent.ergonomics.daily_journal import write_daily_journal
from teaagent.ergonomics.guidance import collect_workspace_guidance
from teaagent.ergonomics.status_short import build_status_short
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.recipes.registry import list_recipes, run_recipe


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
