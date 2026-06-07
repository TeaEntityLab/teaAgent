"""Agent status, list, and show commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory


def agent_status_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        print_json(store.heartbeat_for_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def agent_runs_list(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    payload = [summary.to_dict() for summary in store.list_runs(limit=args.limit)]
    from teaagent.scratchpad import Scratchpad

    scratchpad = Scratchpad(Path(args.root))
    if scratchpad.exists():
        content = scratchpad.read()
        if content and content.get('last_goal'):
            payload.append({'scratchpad_last_goal': content['last_goal']})
    print_json(payload)
    return 0


def agent_runs_trace(args: argparse.Namespace) -> int:
    from teaagent.run_trace import build_run_trace, format_trace_text

    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    trace = build_run_trace(events)
    if getattr(args, 'text', False):
        print(format_trace_text(trace))
        return 0
    print_json({'run_id': args.run_id, 'trace': trace})
    return 0


def agent_runs_export(args: argparse.Namespace) -> int:
    from teaagent.run_trace import dumps_export, export_run

    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print(dumps_export(export_run(events, run_id=args.run_id)))
    return 0


def agent_runs_replay(args: argparse.Namespace) -> int:
    from teaagent.run_trace import dumps_export, replay_dry_run

    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print(dumps_export(replay_dry_run(events, run_id=args.run_id)))
    return 0


def agent_run_show(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        print_json(store.show_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0
