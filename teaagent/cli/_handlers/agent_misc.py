"""Miscellaneous agent commands (plan, daily, card, attach, undo, etc.)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from teaagent.cli import EXIT_BLOCKING, EXIT_SUCCESS
from teaagent.cli._output import print_json
from teaagent.run_store import RunStore

from .agent_helpers import _prepare_task


def agent_plan_command(args: argparse.Namespace) -> int:
    from teaagent.plan import load_plan_contract

    try:
        contract = load_plan_contract(
            args.plan_file,
            root=args.root,
            allow_external_plan=getattr(args, 'allow_external_plan', False),
        )
    except (FileNotFoundError, ValueError) as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    if getattr(args, 'validate', False):
        errors = contract.validate()  # type: ignore[attr-defined]
        if errors:
            print_json({'status': 'invalid', 'errors': errors})
            return 1
        print_json({'status': 'valid', 'plan': contract.to_dict()})
        return 0

    if getattr(args, 'dry_run', False):
        from teaagent.ergonomics.dry_run import build_dry_run_payload

        payload = build_dry_run_payload(
            task=contract.task,
            root=args.root,
            provider=args.provider,
            model=args.model,
            permission_mode=args.permission_mode,
            route=getattr(args, 'route_model', False),
            context_profile=getattr(args, 'context_profile', 'balanced'),
        )
        print_json(payload)
        return 0

    # Execute the plan
    from .agent_run import agent_run_task

    # Set up args for execution
    exec_args = argparse.Namespace(
        root=args.root,
        task=contract.task,
        from_plan=args.plan_file,
        allow_external_plan=getattr(args, 'allow_external_plan', False),
        provider=args.provider,
        model=args.model,
        permission_mode=args.permission_mode,
        route_model=getattr(args, 'route_model', False),
        max_iterations=getattr(args, 'max_iterations', 100),
        max_tool_calls=getattr(args, 'max_tool_calls', 500),
        clarify=getattr(args, 'clarify', False),
        allow_destructive=getattr(args, 'allow_destructive', False),
        approve_call_id=[],
        hitl_approval=getattr(args, 'hitl_approval', False),
        subagent=getattr(args, 'subagent', False),
        max_subagent_depth=getattr(args, 'max_subagent_depth', 3),
        heartbeat=getattr(args, 'heartbeat', 30),
        code_analysis=getattr(args, 'code_analysis', False),
        context_profile=getattr(args, 'context_profile', 'balanced'),
        skill=getattr(args, 'skill', None),
        no_auto_skills=getattr(args, 'no_auto_skills', False),
        max_estimated_cost_cents=getattr(args, 'max_estimated_cost_cents', 1000),
        background=False,
        dry_run=False,
        gate_approved=getattr(args, 'gate_approved', False),
        git_sandbox_auto_stash=getattr(args, 'git_sandbox_auto_stash', False),
        telemetry_otlp_endpoint=getattr(args, 'telemetry_otlp_endpoint', None),
        telemetry_service_name=getattr(args, 'telemetry_service_name', 'teaagent'),
        telemetry_console=getattr(args, 'telemetry_console', False),
        checkpoint_store=getattr(args, 'checkpoint_store', None),
        auto_compact=getattr(args, 'auto_compact', None),
        human=getattr(args, 'human', False),
        notify=getattr(args, 'notify', False),
        json_stream=getattr(args, 'json_stream', False),
        _adapter_factory=getattr(args, '_adapter_factory', None),
    )

    return agent_run_task(exec_args)


def agent_preflight_command(args: argparse.Namespace) -> int:
    from teaagent.preflight import preflight

    task = _prepare_task(args, args.task)
    result = preflight(task, root=args.root, provider=args.provider)
    payload = result.to_dict()
    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_preflight_summary

        print(format_preflight_summary(payload, root=args.root))
    else:
        print_json(payload)
    return EXIT_SUCCESS if result.to_dict()['ready'] else EXIT_BLOCKING


def agent_daily_command(args: argparse.Namespace) -> int:
    if getattr(args, 'stale_check', False):
        from teaagent.cockpit import assess_stale_workspace

        report = assess_stale_workspace(args.root)
        print_json(report.to_dict())
        return (
            EXIT_SUCCESS
            if not report.dirty_git and not report.diverged_from_main
            else EXIT_BLOCKING
        )

    from teaagent.daily import build_daily_brief

    brief = build_daily_brief(
        task=getattr(args, 'task', None),
        root=args.root,
        provider=getattr(args, 'provider', 'gpt'),
        model=getattr(args, 'model', None),
    )
    banner = None
    if getattr(args, 'whats_new', False):
        from teaagent.whats_new import get_whats_new_banner

        banner = get_whats_new_banner()
    payload = brief.to_dict()
    if banner:
        payload['whats_new'] = banner
    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root, title='TeaAgent daily'))
    else:
        print_json(payload)
    return 0 if brief.ready else 2


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


def agent_attach_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        heartbeat = store.heartbeat_for_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    pending = store.pending_approval_for_run(args.run_id)
    if getattr(args, 'resume', False):
        from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

        defaults = load_workspace_defaults(args.root)
        provider = defaults.get('provider')
        if not provider:
            print_json({'status': 'error', 'message': 'provider required for --resume'})
            return 1
        from .agent_run import agent_resume_command

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
            audit_dict_to_stream_event,
            emit_stream_event,
        )

        if not getattr(args, 'json_stream', False):
            print_json(
                {
                    'run_id': args.run_id,
                    'status': heartbeat.get('status', 'unknown'),
                    'pending_approval': pending,
                }
            )
        for raw_event in stream_run_events(
            args.run_id,
            root=args.root,
            follow=True,
        ):
            if getattr(args, 'json_stream', False):
                event = audit_dict_to_stream_event(raw_event)
                if event is not None:
                    emit_stream_event(event)
        return 0
    print_json(
        {
            'run_id': args.run_id,
            'status': heartbeat.get('status', 'unknown'),
            'pending_approval': pending,
        }
    )
    return 0


def agent_undo_command(args: argparse.Namespace) -> int:
    import base64
    import difflib

    from teaagent.run_undo import UndoJournal
    from teaagent.sandbox import GitBranchSandbox

    store = RunStore(args.root)
    run_id = getattr(args, 'run_id', None)
    if run_id is None or getattr(args, 'last', False):
        run_id = store.latest_run_with_undo()
        if run_id is None:
            print_json(
                {
                    'status': 'error',
                    'message': 'no undo journal found for recent runs',
                }
            )
            return 1

    # Try git sandbox rollback first
    git_sandbox = GitBranchSandbox(args.root, run_id=run_id)
    if git_sandbox.is_available():
        rollback_result = git_sandbox.rollback()
        if rollback_result.success:
            print_json(
                {
                    'status': 'restored',
                    'method': 'git',
                    'run_id': run_id,
                    'branch': rollback_result.branch_name,
                }
            )
            return 0
        else:
            print(
                f'[TeaAgent WARNING] Git rollback failed: {rollback_result.error}, falling back to UndoJournal',
                file=sys.stderr,
            )

    # Fallback to UndoJournal
    undo_path = store.undo_path(run_id)
    if not undo_path.is_file():
        print_json(
            {
                'status': 'error',
                'message': f"no undo journal for run '{run_id}'",
                'run_id': run_id,
            }
        )
        return 1
    journal = UndoJournal(args.root, path=undo_path)

    if getattr(args, 'preview', False):
        root_path = Path(args.root).resolve()
        out: list[str] = []
        for entry in journal.iter_entries():
            rel_path = entry.get('path')
            if not isinstance(rel_path, str) or not rel_path:
                continue
            existed_before = bool(entry.get('existed_before'))
            abs_path = (root_path / rel_path).resolve()
            if not str(abs_path).startswith(str(root_path)):
                continue
            if not existed_before:
                out.append(f'--- {rel_path} (would be deleted)')
                continue
            before_b64 = entry.get('content_b64')
            if not isinstance(before_b64, str) or not before_b64:
                continue
            try:
                before_bytes = base64.b64decode(before_b64)
            except Exception:
                continue
            try:
                before_text = before_bytes.decode('utf-8')
            except UnicodeDecodeError:
                out.append(f'--- {rel_path} (binary restore)')
                continue
            try:
                after_text = (
                    abs_path.read_text(encoding='utf-8') if abs_path.is_file() else ''
                )
            except UnicodeDecodeError:
                out.append(f'--- {rel_path} (binary current)')
                continue
            before_lines = before_text.splitlines(keepends=True)
            after_lines = after_text.splitlines(keepends=True)
            out.extend(
                difflib.unified_diff(
                    after_lines,
                    before_lines,
                    fromfile=f'a/{rel_path}',
                    tofile=f'b/{rel_path}',
                )
            )
        print(''.join(out) if out else '(no undo diff available)')
        return 0

    result = journal.restore()
    status = 'restored' if result.ok else 'partial'
    rel_undo = undo_path.resolve().relative_to(store.root).as_posix()
    payload = {
        'status': status,
        'method': 'journal',
        'run_id': run_id,
        'restored': result.restored,
        'deleted': result.deleted,
        'errors': result.errors,
        'audit_recorded': store.record_undo_applied(
            run_id,
            status=status,
            restored=result.restored,
            deleted=result.deleted,
            errors=result.errors,
            undo_journal_path=rel_undo,
        ),
    }
    if result.ok:
        undo_path.unlink(missing_ok=True)
    print_json(payload)
    return 0 if result.ok else 1


def background_list_command(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import BackgroundRunStore

    store = BackgroundRunStore(args.root)
    print_json(store.list())
    return 0


def background_show_command(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import BackgroundRunStore

    store = BackgroundRunStore(args.root)
    try:
        print_json(store.get(args.background_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0
