from __future__ import annotations

import argparse
import sys
from pathlib import Path

from teaagent.approval import parse_permission_mode
from teaagent.cli._handlers._misc import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.ergonomics.run_history import list_recall_runs, list_yesterday_runs
from teaagent.ergonomics.status_short import build_status_short
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults


def _truncate_string(s: str, max_len: int = 40, suffix: str = '...') -> str:
    """Truncate a string to max_len, adding suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix


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
    runs = (
        AgentExecutionFactory(args.root)
        .create_background_run_store(readonly=True)
        .list()
    )
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
    try:
        print_json(
            AgentExecutionFactory(args.root)
            .create_background_run_store(readonly=True)
            .get(args.background_id)
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def session_list_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
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
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
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
