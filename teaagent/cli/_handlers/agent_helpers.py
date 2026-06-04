"""Helper functions for agent handlers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from teaagent.plan import PlanContract
from teaagent.runner import ApprovalHandler, ApprovalRequest, RunResult


def _resolve_selected_skills(args: argparse.Namespace) -> Optional[frozenset[str]]:
    if getattr(args, 'no_auto_skills', False):
        return frozenset()
    names = [
        str(item).strip()
        for item in (getattr(args, 'skill', None) or [])
        if str(item).strip()
    ]
    if names:
        return frozenset(names)
    return None


def _emit_readiness_payload(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    from teaagent.cli._output import print_json

    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root))
        return
    print_json(payload)


def _resolve_run_task(
    args: argparse.Namespace,
) -> tuple[str, Optional[PlanContract]]:
    from teaagent.plan import load_plan_contract

    plan_contract: PlanContract | None = None
    if getattr(args, 'from_plan', None):
        plan_contract = load_plan_contract(
            args.from_plan,
            root=args.root,
            allow_external_plan=getattr(args, 'allow_external_plan', False),
        )
        raw_task = plan_contract.task
    elif getattr(args, 'task', None):
        raw_task = args.task
    else:
        raise ValueError('task or --from-plan is required')
    return _prepare_task(args, raw_task), plan_contract


def _prepare_task(args: argparse.Namespace, task: str) -> str:
    from teaagent.ergonomics.context_inject import expand_at_references
    from teaagent.ergonomics.daily_cost import check_daily_cost_cap
    from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

    expanded, _refs = expand_at_references(task, root=args.root)
    defaults = load_workspace_defaults(args.root)
    cap = int(defaults.get('daily_cost_cap_cents') or 0)
    check_daily_cost_cap(args.root, cap)
    return expanded


def _resolve_auto_compact(args: argparse.Namespace) -> bool:
    if getattr(args, 'auto_compact', None) is not None:
        return bool(args.auto_compact)
    from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

    defaults = load_workspace_defaults(getattr(args, 'root', '.'))
    return bool(defaults.get('auto_compact_on_resume', True))


def _save_git_sandbox_consent(root: str | Path, value: str) -> None:
    root_path = Path(root).resolve()
    tea_dir = root_path / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)
    json_path = tea_dir / 'config.json'
    config = {}
    if json_path.is_file():
        from contextlib import suppress

        with suppress(Exception):
            config = json.loads(json_path.read_text(encoding='utf-8'))
    config['git_sandbox_consent'] = value
    try:
        json_path.write_text(
            json.dumps(config, sort_keys=True, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        print(f'Warning: Failed to save configuration: {exc}', file=sys.stderr)


def run_result_payload(
    result: RunResult,
    *,
    routing: Optional[dict[str, Any]],
    audit_summary: Optional[dict[str, Any]] = None,
    permission_mode: Optional[str] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'run_id': result.run_id,
        'status': result.status,
        'iterations': result.iterations,
        'tool_calls': result.tool_calls,
        'input_tokens': result.input_tokens,
        'output_tokens': result.output_tokens,
        'routing': routing,
        'final_answer': result.final_answer.content if result.final_answer else None,
    }
    if permission_mode is not None:
        payload['permission_mode'] = permission_mode
        payload['run_mode'] = (
            'planning' if permission_mode == 'read-only' else 'execution'
        )
    if audit_summary is not None:
        payload['audit_summary'] = audit_summary
    if 'approval' in result.metadata:
        payload['approval'] = result.metadata['approval']
    return payload


def make_cli_approval_handler(
    root: str | Path, *, permission_mode: str = 'prompt'
) -> ApprovalHandler:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    store = ApprovalPresetStore(root)

    def _handler(request: ApprovalRequest) -> bool:
        if store.is_allowed(
            request.tool_name,
            permission_mode=permission_mode,
            arguments=request.arguments,
        ):
            return True
        print(
            json.dumps(
                {'status': 'approval_required', 'approval': request.to_dict()},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        print(
            f'Approve {request.call_id} ({request.tool_name})? [y]es / [n]o / always for this [p]ath / always for this [t]ool / [s]top run: ',
            end='',
            file=sys.stderr,
        )
        answer = input().strip().lower()
        if answer in {'y', 'yes'}:
            return True
        elif answer in {'s', 'stop'}:
            print('[TeaAgent] Operator aborted task execution.', file=sys.stderr)
            raise SystemExit('Task aborted by operator.')
        elif answer == 'p':
            path = None
            if request.arguments:
                for key in ('path', 'TargetFile', 'target_file', 'AbsolutePath'):
                    candidate = request.arguments.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        path = candidate
                        break
            if path:
                store.grant(
                    request.tool_name,
                    scope='session',
                    permission_mode=permission_mode,
                    path_globs=[str(path)],
                    ttl_hours=8.0,
                )
                print(
                    f'[TeaAgent] Granted {request.tool_name} for path {path} (session)',
                    file=sys.stderr,
                )
                return True
            else:
                print(
                    '[TeaAgent] No path found in arguments; path-scoped grant not created',
                    file=sys.stderr,
                )
                return False
        elif answer == 't':
            # DS-12: Provide explicit current directory pattern to prevent implicit global grants
            store.grant(
                request.tool_name,
                scope='session',
                permission_mode=permission_mode,
                path_globs=['*'],  # Explicit current directory
                ttl_hours=8.0,
            )
            print(
                f'[TeaAgent] Granted {request.tool_name} for current directory (session)',
                file=sys.stderr,
            )
            return True
        return False

    return _handler
