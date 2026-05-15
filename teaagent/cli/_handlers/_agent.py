from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.intent import build_task_spec, clarify_task
from teaagent.model_routing import route_model
from teaagent.policy import parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore, summarize_audit_events
from teaagent.runner import ApprovalRequest, RunResult


def agent_run_task(args: argparse.Namespace) -> int:
    return _execute_agent_task(args, args.task)


def agent_resume_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        original_task = store.task_for_run(args.run_id)
    except (FileNotFoundError, ValueError) as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    initial_observations: list[dict[str, Any]] = []
    initial_context_extra: Optional[dict[str, Any]] = None
    auto_approved: Optional[str] = None

    if not args.fresh_restart:
        checkpoint_path = getattr(args, 'checkpoint_store', None)
        checkpoint = None
        if checkpoint_path:
            from teaagent.checkpoint import SQLiteCheckpointStore

            checkpoint = SQLiteCheckpointStore(checkpoint_path).load(args.run_id)
        if checkpoint is not None:
            initial_observations = checkpoint.get('observations', [])
            initial_context_extra = {
                k: v for k, v in checkpoint.items() if k not in ('task', 'observations')
            }
        else:
            initial_observations = store.observations_for_run(args.run_id)
        pending = store.pending_approval_for_run(args.run_id)
        if pending and pending['call_id'] not in args.approve_call_id:
            args.approve_call_id = list(args.approve_call_id) + [pending['call_id']]
            auto_approved = pending['call_id']

    return _execute_agent_task(
        args,
        original_task,
        resumed_from=args.run_id,
        initial_observations=initial_observations,
        initial_context_extra=initial_context_extra,
        auto_approved_call_id=auto_approved,
    )


def _execute_agent_task(
    args: argparse.Namespace,
    task: str,
    *,
    resumed_from: Optional[str] = None,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    initial_context_extra: Optional[dict[str, Any]] = None,
    auto_approved_call_id: Optional[str] = None,
) -> int:
    task_spec = None
    if args.clarify:
        clarification = clarify_task(task)
        if clarification.needs_clarification:
            print_json(
                {
                    'status': 'needs_clarification',
                    'clarification': clarification.to_dict(),
                }
            )
            return 2
        task_spec = build_task_spec(task, clarification)

    routing = (
        route_model(task, provider=args.provider, model=args.model)
        if args.route_model
        else None
    )
    selected_model = routing.model if routing else args.model
    adapter = args._adapter_factory(args.provider, model=selected_model)  # type: ignore[attr-defined]
    store = RunStore(args.root)
    audit = store.audit_logger()

    _telemetry_sink = None
    if getattr(args, 'telemetry_otlp_endpoint', None) or getattr(
        args, 'telemetry_console', False
    ):
        try:
            from teaagent.telemetry import (
                TelemetryConfig,
                TracingHTTPTransport,
                configure_telemetry,
            )

            cfg = TelemetryConfig(
                service_name=getattr(args, 'telemetry_service_name', 'teaagent'),
                otlp_endpoint=getattr(args, 'telemetry_otlp_endpoint', None),
                console=getattr(args, 'telemetry_console', False),
            )
            _telemetry_sink, tracer = configure_telemetry(cfg)
            audit.add_sink(_telemetry_sink.handle_event)
            adapter = args._adapter_factory(  # type: ignore[attr-defined]
                args.provider,
                model=selected_model,
                transport=TracingHTTPTransport(adapter.transport, tracer),  # type: ignore[attr-defined]
            )
        except Exception as exc:
            print(f'Telemetry setup failed: {exc}', file=sys.stderr)

    approval_handler = cli_approval_handler if args.hitl_approval else None
    checkpoint_store = None
    checkpoint_path = getattr(args, 'checkpoint_store', None)
    if checkpoint_path:
        from teaagent.checkpoint import SQLiteCheckpointStore

        checkpoint_store = SQLiteCheckpointStore(checkpoint_path)
    resolved_permission_mode = parse_permission_mode(args.permission_mode)
    result = run_chat_agent(
        task=task,
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            args.root,
            max_iterations=args.max_iterations,
            max_tool_calls=args.max_tool_calls,
            allow_destructive=args.allow_destructive,
            model=selected_model,
            permission_mode=resolved_permission_mode,
            approved_call_ids=frozenset(args.approve_call_id),
            enable_subagent=args.subagent,
            max_subagent_depth=args.max_subagent_depth,
            heartbeat_seconds=args.heartbeat,
            approval_handler=approval_handler,
            checkpoint_store=checkpoint_store,
        ),
        audit=audit,
        task_spec=task_spec,
        initial_observations=initial_observations,
        initial_context_extra=initial_context_extra,
    )
    store.logger_for_result(result, audit)
    if _telemetry_sink is not None:
        from contextlib import suppress

        with suppress(Exception):
            _telemetry_sink.force_flush()
    events = store.show_run(result.run_id)
    payload = run_result_payload(
        result,
        routing=routing.to_dict() if routing else None,
        audit_summary=summarize_audit_events(events),
        permission_mode=resolved_permission_mode.value,
    )
    if resumed_from:
        payload['resumed_from'] = resumed_from
        payload['task'] = task
        if initial_observations:
            payload['replayed_observations'] = len(initial_observations)
        if auto_approved_call_id is not None:
            payload['auto_approved_call_id'] = auto_approved_call_id
    print_json(payload)
    return 0 if result.status == 'completed' else 1


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
        'routing': routing,
        'final_answer': result.final_answer.content if result.final_answer else None,
    }
    if permission_mode is not None:
        payload['permission_mode'] = permission_mode
        payload['run_mode'] = 'planning' if permission_mode == 'read-only' else 'execution'
    if audit_summary is not None:
        payload['audit_summary'] = audit_summary
    if 'approval' in result.metadata:
        payload['approval'] = result.metadata['approval']
    return payload


def cli_approval_handler(request: ApprovalRequest) -> bool:
    print(
        json.dumps(
            {'status': 'approval_required', 'approval': request.to_dict()},
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    print(
        f'Approve destructive tool call {request.call_id} ({request.tool_name})? [y/N] ',
        end='',
        file=sys.stderr,
    )
    answer = input()
    return answer.strip().lower() in {'y', 'yes'}


def agent_preflight_command(args: argparse.Namespace) -> int:
    report = preflight(
        args.task,
        root=args.root,
        provider=args.provider,
        model=args.model,
        permission_mode=parse_permission_mode(args.permission_mode),
        route=args.route_model,
        memory_limit=args.memory_limit,
    )
    print_json(report.to_dict())
    return 0 if report.to_dict()['ready'] else 2


def agent_status_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        print_json(store.heartbeat_for_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def agent_runs_list(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json([summary.to_dict() for summary in store.list_runs(limit=args.limit)])
    return 0


def agent_run_show(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json(store.show_run(args.run_id))
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


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
