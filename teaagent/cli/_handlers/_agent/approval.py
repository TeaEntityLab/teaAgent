from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from teaagent.runner import ApprovalHandler, ApprovalRequest, RunResult

DEFAULT_SESSION_GRANT_TTL_HOURS = 8.0


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
                    ttl_hours=DEFAULT_SESSION_GRANT_TTL_HOURS,
                )
                print(
                    f'[TeaAgent] Registered session grant for {request.tool_name} matching path: {path}',
                    file=sys.stderr,
                )
            else:
                print(
                    f'[TeaAgent] No path found in tool arguments; path-scoped grant not created for {request.tool_name}',
                    file=sys.stderr,
                )
                return False
            return True
        elif answer == 't':
            # Use explicit current-directory pattern to prevent implicit global grants
            store.grant(
                request.tool_name,
                scope='session',
                permission_mode=permission_mode,
                path_globs=['*'],  # Explicit current directory
                ttl_hours=8.0,
            )
            print(
                f'[TeaAgent] Registered session grant for {request.tool_name} (current directory)',
                file=sys.stderr,
            )
            return True
        return False

    return _handler


def make_cli_budget_prompt_handler() -> Callable[[dict[str, Any]], bool]:
    def _handler(payload: dict[str, Any]) -> bool:
        percent = float(payload.get('percent', 0.0))
        cost_cents = float(payload.get('cost_cents', 0.0))
        max_cost_cents = float(payload.get('max_cost_cents', 0.0))
        spent = cost_cents / 100.0
        cap = max_cost_cents / 100.0
        print(
            json.dumps(
                {
                    'status': 'budget_prompt',
                    'percent': percent,
                    'spent_usd': spent,
                    'cap_usd': cap,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        print(
            f'[TeaAgent] Budget at {percent:.0f}% (${spent:.2f} / ${cap:.2f}). Continue? [y/N]: ',
            end='',
            file=sys.stderr,
        )
        answer = input().strip().lower()
        return answer in {'y', 'yes'}

    return _handler


def cli_approval_handler(request: ApprovalRequest) -> bool:
    """Default handler for cwd workspace; prefer ``make_cli_approval_handler(root)``."""
    return make_cli_approval_handler('.')(request)
