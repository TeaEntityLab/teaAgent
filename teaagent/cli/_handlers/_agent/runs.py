from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from teaagent.approval import parse_permission_mode
from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.ergonomics.cli_output import wants_human_cli
from teaagent.integration.run_state import build_attach_snapshot
from teaagent.types import PermissionMode

from .resume import agent_resume_command
from .run import _emit_readiness_payload


def agent_attach_command(args: argparse.Namespace) -> int:  # noqa: C901
    store = AgentExecutionFactory(args.root).create_run_store()
    try:
        snapshot = build_attach_snapshot(store, args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    run_state = snapshot['run_state']
    pending = snapshot['pending_approval']
    if getattr(args, 'resume', False):
        from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

        defaults = load_workspace_defaults(args.root)
        provider = defaults.get('provider')
        if not provider:
            print_json({'status': 'error', 'message': 'provider required for --resume'})
            return 1
        resume_args = argparse.Namespace(
            run_id=args.run_id,
            root=args.root,
            provider=provider,
            model=defaults.get('model'),
            fresh_restart=False,
            approve_call_id=[],
            clarify=False,
            route_model=False,
            max_iterations=int(defaults.get('max_iterations', 10)),
            max_tool_calls=int(defaults.get('max_tool_calls', 10)),
            allow_destructive=False,
            hitl_approval=False,
            permission_mode=defaults.get('permission_mode', 'prompt'),
            subagent=False,
            max_subagent_depth=1,
            heartbeat=float(defaults.get('heartbeat', 0.0)),
            code_analysis=False,
            telemetry_otlp_endpoint=None,
            telemetry_service_name='teaagent',
            telemetry_console=False,
            checkpoint_store=None,
            auto_compact=None,
            _adapter_factory=getattr(args, '_adapter_factory', None),
        )
        return agent_resume_command(resume_args)
    if getattr(args, 'follow', False):
        from teaagent.ergonomics.session_stream import stream_run_events
        from teaagent.streaming.events import (
            StreamEvent,
            audit_dict_to_stream_event,
            emit_stream_event,
        )

        if not getattr(args, 'json_stream', False):
            print_json(
                {
                    'run_id': args.run_id,
                    'run_state': run_state,
                    'heartbeat': run_state,
                    'pending_approval': pending,
                    'streaming': True,
                }
            )
        else:
            emit_stream_event(
                StreamEvent(
                    'attach_started',
                    {
                        'run_id': args.run_id,
                        'run_state': run_state,
                        'heartbeat': run_state,
                        'pending_approval': pending,
                    },
                )
            )
        for event in stream_run_events(args.run_id, root=args.root, follow=True):
            if getattr(args, 'json_stream', False):
                mapped = audit_dict_to_stream_event(event)
                if mapped is not None:
                    emit_stream_event(mapped)
                continue
            print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)
        if getattr(args, 'notify', False):
            from teaagent.ergonomics.notify import notify

            notify('TeaAgent', f'Run {args.run_id}: {run_state.get("status")}')
        return 0
    print_json(snapshot)
    if getattr(args, 'notify', False):
        from teaagent.ergonomics.notify import notify

        notify('TeaAgent', f'Run {args.run_id}: {run_state.get("status")}')
    return 0


def agent_daily_command(args: argparse.Namespace) -> int:
    if getattr(args, 'dry_run', False):
        task = args.task or 'daily readiness check'
        from teaagent.ergonomics.dry_run import build_dry_run_payload

        payload = build_dry_run_payload(
            task=task,
            root=args.root,
            provider=args.provider,
            model=args.model,
            permission_mode=parse_permission_mode(args.permission_mode),
            route=args.route_model,
            memory_limit=args.memory_limit,
            context_profile=args.context_profile,
            runs_limit=args.runs_limit,
        )
        _emit_readiness_payload(args, payload)
        ready = payload.get('would_invoke_model', False)
        return 0 if ready or not wants_human_cli(args) else 2
    permission_mode = parse_permission_mode(args.permission_mode)
    from teaagent.daily import build_daily_brief

    brief = build_daily_brief(
        task=args.task,
        root=args.root,
        provider=args.provider,
        model=args.model,
        permission_mode=permission_mode,
        route=args.route_model,
        memory_limit=args.memory_limit,
        runs_limit=args.runs_limit,
        context_profile=args.context_profile,
        readonly=(permission_mode == PermissionMode.READ_ONLY),
    )
    if getattr(args, 'write_journal', False):
        from teaagent.ergonomics.daily_journal import write_daily_journal

        write_daily_journal(brief, root=args.root)
    from teaagent.ergonomics.whats_new import whats_new_banner

    banner = whats_new_banner(args.root)
    payload = brief.to_dict()
    if banner:
        payload['whats_new'] = banner
    if wants_human_cli(args):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root, title='TeaAgent daily'))
    else:
        print_json(payload)
    return 0 if brief.ready else 2


def agent_status_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        if getattr(args, 'progress', False):
            from teaagent.run_progress import (
                build_run_progress_summary,
                format_run_progress_summary,
            )

            summary = build_run_progress_summary(store, args.run_id)
            if wants_human_cli(args):
                print(format_run_progress_summary(summary))
            else:
                print_json(summary.to_dict())
            return 0
        if getattr(args, 'evidence', False):
            if wants_human_cli(args):
                from teaagent.run_receipt import build_run_receipt

                print(build_run_receipt(store, args.run_id, args.root))
                return 0
            from teaagent.evidence_summary import build_evidence_summary

            evidence_summary = build_evidence_summary(store, args.run_id, args.root)
            print_json(evidence_summary.to_dict())
            return 0
        print_json(store.heartbeat_for_run(args.run_id))
    except FileNotFoundError as exc:
        if wants_human_cli(args):
            from teaagent.cli._formatting import format_error_block

            print(
                format_error_block('Error', str(exc), category='NOT_FOUND'),
                file=sys.stderr,
            )
            return 1
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
    # Handle --diff flag to show git diff of changes
    if getattr(args, 'diff', False):
        return _show_run_diff(args)

    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        print_json(store.show_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def _show_run_diff(args: argparse.Namespace) -> int:  # noqa: C901
    """Show git diff of changes made in a run."""
    import json
    from pathlib import Path

    root = Path(args.root).resolve()
    undo_path = root / '.teaagent' / 'undo' / f'{args.run_id}.jsonl'

    if not undo_path.exists():
        print_json(
            {
                'status': 'error',
                'message': f'No undo journal found for run {args.run_id}',
            }
        )
        return 1

    # Read undo journal to get changed files
    changed_files: list[str] = []
    for line in undo_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        p = obj.get('path')
        if isinstance(p, str) and p:
            changed_files.append(p)

    if not changed_files:
        print('No files changed in this run.')
        return 0

    print(f'Changes from run {args.run_id}:')
    print()

    # Show diff for each file
    for file_path in changed_files:
        full_path = root / file_path
        if not full_path.exists():
            print(f'{file_path} (deleted)')
            continue

        try:
            result = subprocess.run(
                ['git', 'diff', '--', str(full_path)],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                print(f'--- {file_path}')
                print(result.stdout)
            else:
                print(f'{file_path} (new file)')
        except subprocess.SubprocessError:
            print(f'{file_path} (unable to show diff)')

    return 0


def agent_runs_commit_command(args: argparse.Namespace) -> int:  # noqa: C901
    """Commit changes from a run with metadata."""
    from pathlib import Path

    root = Path(args.root).resolve()

    # Get run_id from args or use last run
    run_id = getattr(args, 'run_id', None)
    if not run_id:
        # Get last run from RunStore
        store = AgentExecutionFactory(root).create_run_store(readonly=True)
        runs = store.list_runs(limit=1)
        if not runs:
            print_json({'status': 'error', 'message': 'No runs found to commit'})
            return 1
        run_id = runs[0].run_id

    undo_path = root / '.teaagent' / 'undo' / f'{run_id}.jsonl'
    if not undo_path.exists():
        print_json(
            {'status': 'error', 'message': f'No undo journal found for run {run_id}'}
        )
        return 1

    # Check if git repo
    try:
        subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=root,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print_json({'status': 'error', 'message': 'Not a git repository'})
        return 1

    # Stage all changes
    try:
        subprocess.run(['git', 'add', '-A'], cwd=root, check=True)
    except subprocess.CalledProcessError as e:
        print_json({'status': 'error', 'message': f'Failed to stage changes: {e}'})
        return 1

    # Generate commit message
    custom_message = getattr(args, 'message', None)
    if custom_message:
        commit_message = custom_message
    else:
        # Auto-generate commit message with run metadata
        store = AgentExecutionFactory(root).create_run_store(readonly=True)
        try:
            events = store.show_run(run_id)
            # Extract task from first event
            task = 'TeaAgent run'
            for event in events:
                if event.get('event_type') == 'run_started':
                    task = event.get('payload', {}).get('task', 'TeaAgent run')
                    break
            commit_message = f'teaagent: {task}\n\nRun ID: {run_id}'
        except FileNotFoundError:
            commit_message = f'teaagent: changes from run {run_id}'

    # Commit
    try:
        subprocess.run(
            ['git', 'commit', '-m', commit_message],
            cwd=root,
            check=True,
        )
        print_json(
            {
                'status': 'committed',
                'run_id': run_id,
                'message': commit_message,
            }
        )
    except subprocess.CalledProcessError as e:
        # Check if nothing to commit
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            print_json(
                {
                    'status': 'nothing_to_commit',
                    'run_id': run_id,
                    'message': 'No changes to commit (idempotent)',
                }
            )
            return 0
        print_json({'status': 'error', 'message': f'Failed to commit: {e}'})
        return 1

    return 0


def agent_card_command(args: argparse.Namespace) -> int:
    from teaagent import __version__
    from teaagent.agentcard import build_self_card
    from teaagent.workspace_tools import build_workspace_tool_registry

    registry = build_workspace_tool_registry(args.root)
    card = build_self_card(
        name=getattr(args, 'agent_name', 'teaagent'),
        version=__version__,
        registry=registry,
        endpoint=getattr(args, 'endpoint', None),
    )
    print_json(card.to_dict())
    return 0
