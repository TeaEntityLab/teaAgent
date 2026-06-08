from __future__ import annotations

import argparse
import base64
import difflib
import subprocess
from pathlib import Path

from teaagent.approval import parse_permission_mode
from teaagent.cli._output import print_json
from teaagent.ergonomics.human_output import format_preflight_summary
from teaagent.preflight import preflight
from teaagent.types import PermissionMode


def agent_preflight_command(args: argparse.Namespace) -> int:
    permission_mode = parse_permission_mode(args.permission_mode)
    report = preflight(
        args.task,
        root=args.root,
        provider=args.provider,
        model=args.model,
        permission_mode=permission_mode,
        route=args.route_model,
        memory_limit=args.memory_limit,
        context_profile=args.context_profile,
        readonly=(permission_mode == PermissionMode.READ_ONLY),
    )
    if args.human:
        print(format_preflight_summary(report.to_dict(), root=args.root))
    else:
        print_json(report.to_dict())
    return 0 if report.to_dict()['ready'] else 2


def agent_plan_command(args: argparse.Namespace) -> int:
    from teaagent.plan import write_plan_artifact

    permission_mode = parse_permission_mode(args.permission_mode)
    report = preflight(
        args.task,
        root=args.root,
        provider=args.provider,
        model=args.model,
        permission_mode=permission_mode,
        route=args.route_model,
        memory_limit=args.memory_limit,
        context_profile=args.context_profile,
        readonly=(permission_mode == PermissionMode.READ_ONLY),
    )
    payload = report.to_dict()
    if not getattr(args, 'no_write', False):
        artifact = write_plan_artifact(report, root=args.root)
        payload['plan_artifact'] = str(artifact)
    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root))
        if payload.get('plan_artifact'):
            print(f'\nPlan saved: {payload["plan_artifact"]}')
        return 0 if payload.get('ready') else 2
    print_json(payload)
    return 0 if payload.get('ready') else 2


def agent_undo_command(args: argparse.Namespace) -> int:  # noqa: C901
    from teaagent.cli.execution import AgentExecutionFactory

    factory = AgentExecutionFactory(args.root)
    store = factory.create_run_store()
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

    preview = getattr(args, 'preview', False)

    # Try git sandbox rollback first
    git_sandbox = factory.create_git_sandbox(run_id=run_id)
    if git_sandbox.is_available():
        if preview:
            root_path = Path(args.root).resolve()
            try:
                diff_result = subprocess.run(
                    [
                        'git',
                        'diff',
                        git_sandbox._branch_name,
                        git_sandbox._original_branch or 'HEAD',
                    ],
                    cwd=root_path,
                    capture_output=True,
                    text=True,
                )
                if diff_result.stdout.strip():
                    print(diff_result.stdout)
                else:
                    print('(no undo diff available)')
            except (subprocess.CalledProcessError, FileNotFoundError):
                print('(unable to generate git diff preview)')
            return 0

        rollback_result = git_sandbox.rollback()
        if rollback_result.success:
            store.record_undo_applied(
                run_id,
                status='restored',
                restored=[],
                deleted=[],
                errors=[],
            )
            print_json(
                {
                    'status': 'restored',
                    'method': 'checkpoint',
                    'mechanism': 'checkpoint restore',
                    'run_id': run_id,
                    'branch': rollback_result.branch_name,
                }
            )
            return 0
        else:
            import sys as _sys

            print(
                f'[TeaAgent WARNING] checkpoint restore failed: {rollback_result.error}, falling back to UndoJournal',
                file=_sys.stderr,
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
    journal = factory.create_undo_journal(path=undo_path)

    if preview:
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
        'mechanism': 'journal undo',
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
