from __future__ import annotations

import argparse
import contextlib
import json
import signal
import sys
import time
from typing import Any, Optional

from teaagent.automations import (
    AutomationSpec,
    AutomationStore,
    AutomationTickLock,
    compute_next_run_at,
)
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.code_analysis import CodeAnalysisConfig
from teaagent.daily import build_daily_brief
from teaagent.intent import build_task_spec, clarify_task
from teaagent.model_routing import route_model
from teaagent.policy import parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore, summarize_audit_events
from teaagent.runner import ApprovalRequest, RunResult
from teaagent.skill_candidates import SkillCandidateStore


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
    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root))
        return
    print_json(payload)


def agent_run_task(args: argparse.Namespace) -> int:
    if getattr(args, 'background', False):
        return _start_background_run(args)
    task = _prepare_task(args, args.task)
    if getattr(args, 'dry_run', False):
        from teaagent.ergonomics.dry_run import build_dry_run_payload

        payload = build_dry_run_payload(
            task=task,
            root=args.root,
            provider=args.provider,
            model=args.model,
            permission_mode=parse_permission_mode(args.permission_mode),
            route=args.route_model,
            context_profile=getattr(args, 'context_profile', 'balanced'),
        )
        _emit_readiness_payload(args, payload)
        ready = payload.get('would_invoke_model', False)
        return 0 if ready or not getattr(args, 'human', False) else 2
    return _execute_agent_task(args, task)


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
            if _resolve_auto_compact(args) and len(initial_observations) > 40:
                initial_observations = initial_observations[-20:]
                initial_context_extra = {
                    'resume_compaction': {
                        'truncated': True,
                        'kept_observations': 20,
                    }
                }
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
    from teaagent.streaming.handlers import (
        adapter_supports_streaming,
        build_run_stream_handlers,
    )

    stream_handlers = build_run_stream_handlers(args, audit)
    use_stream = stream_handlers.stream and adapter_supports_streaming(adapter)
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
            stream=use_stream,
            on_chunk=stream_handlers.on_chunk,
            stream_text_only=stream_handlers.stream_text_only,
            code_analysis_config=(
                CodeAnalysisConfig.from_root(args.root, enabled=True)
                if getattr(args, 'code_analysis', False)
                else None
            ),
            selected_skills=_resolve_selected_skills(args),
            skill_prompt_mode=(
                'index_only' if getattr(args, 'skill_index_only', False) else 'eager'
            ),
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
        if initial_context_extra and initial_context_extra.get('resume_compaction'):
            payload['resume_compaction'] = initial_context_extra['resume_compaction']
        if auto_approved_call_id is not None:
            payload['auto_approved_call_id'] = auto_approved_call_id
    if getattr(args, 'json_stream', False):
        from teaagent.streaming.events import StreamEvent, emit_stream_event

        emit_stream_event(StreamEvent('run_result', payload))
    else:
        print_json(payload)
    if getattr(args, 'notify', False):
        from teaagent.ergonomics.notify import notify

        notify('TeaAgent', f'Run {result.run_id} {result.status}')
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


def cli_approval_handler(request: ApprovalRequest) -> bool:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    store = ApprovalPresetStore('.')
    if store.is_allowed(request.tool_name, permission_mode='prompt'):
        return True
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
        context_profile=args.context_profile,
    )
    print_json(report.to_dict())
    return 0 if report.to_dict()['ready'] else 2


def _start_background_run(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import (
        BackgroundRunStore,
        build_agent_run_command,
    )

    task = _prepare_task(args, args.task)
    command = build_agent_run_command(args, task)
    record = BackgroundRunStore(args.root).start(command)
    payload = record.to_dict()
    payload['status'] = 'background_started'
    payload['attach'] = (
        f'teaagent agent attach <run_id> --follow --root {args.root} '
        '(run_id appears in log when the worker starts)'
    )
    print_json(payload)
    return 0


def _start_automation_background_run(
    *,
    root: str,
    spec: AutomationSpec,
) -> dict[str, Any]:
    from teaagent.ergonomics.background_run import (
        BackgroundRunStore,
        build_agent_run_command,
    )

    run_args = argparse.Namespace(
        root=root,
        provider=spec.provider,
        model=spec.model,
        route_model=False,
        max_iterations=spec.max_iterations,
        max_tool_calls=spec.max_tool_calls,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode=spec.permission_mode,
        subagent=False,
        heartbeat=0.0,
        code_analysis=False,
        context_profile=spec.context_profile,
        selected_skills=list(spec.selected_skills),
    )
    command = build_agent_run_command(run_args, spec.task)
    record = BackgroundRunStore(root).start(
        command, label=f'automation:{spec.automation_id}:{spec.name}'
    )
    return record.to_dict()


def _automation_is_running(root: str, background_id: Optional[str]) -> bool:
    if not background_id:
        return False
    from teaagent.ergonomics.background_run import BackgroundRunStore

    try:
        row = BackgroundRunStore(root).get(background_id)
    except FileNotFoundError:
        return False
    return bool(row.get('alive'))


def _run_automation_once(root: str, spec: AutomationSpec) -> dict[str, Any]:
    from teaagent.automation_collector import run_collector_command

    store = AutomationStore(root)
    if _automation_is_running(root, spec.running_background_id):
        return {
            'automation_id': spec.automation_id,
            'name': spec.name,
            'status': 'skipped_running',
            'running_background_id': spec.running_background_id,
        }
    collector_payload: Optional[dict[str, Any]] = None
    if spec.collector_command.strip():
        collector_payload = run_collector_command(
            spec.collector_command, root=root
        ).to_dict()
        if not collector_payload['wake_agent']:
            updated = store.update(
                AutomationSpec(
                    **{
                        **spec.to_dict(),
                        'last_status': 'skipped_no_wake',
                        'next_run_at': compute_next_run_at(spec.schedule),
                    }
                )
            )
            return {
                'automation_id': spec.automation_id,
                'name': spec.name,
                'status': 'skipped_no_wake',
                'collector': collector_payload,
                'next_run_at': updated.next_run_at,
            }
        if spec.no_agent:
            status = (
                'collector_failed'
                if int(collector_payload['exit_code']) != 0
                else 'collector_ok'
            )
            updated = store.update(
                AutomationSpec(
                    **{
                        **spec.to_dict(),
                        'last_status': status,
                        'next_run_at': compute_next_run_at(spec.schedule),
                    }
                )
            )
            return {
                'automation_id': spec.automation_id,
                'name': spec.name,
                'status': status,
                'collector': collector_payload,
                'next_run_at': updated.next_run_at,
            }
    record = _start_automation_background_run(root=root, spec=spec)
    updated = AutomationSpec(
        **{
            **spec.to_dict(),
            'running_background_id': record['background_id'],
            'last_status': 'background_started',
            'next_run_at': compute_next_run_at(spec.schedule),
        }
    )
    store.update(updated)
    result = {
        'automation_id': spec.automation_id,
        'name': spec.name,
        'status': 'background_started',
        'background_id': record['background_id'],
        'pid': record['pid'],
        'log_path': record['log_path'],
        'next_run_at': updated.next_run_at,
    }
    if collector_payload is not None:
        result['collector'] = collector_payload
    return result


def automation_status_command(args: argparse.Namespace) -> int:
    from teaagent.automations import build_automation_status

    payload = build_automation_status(args.root)
    if getattr(args, 'automation_id', None):
        matches = [
            row
            for row in payload['automations']
            if row['automation_id'] == args.automation_id
        ]
        if not matches:
            print_json(
                {
                    'status': 'error',
                    'message': f"automation '{args.automation_id}' not found",
                }
            )
            return 1
        print_json({'status': 'ok', 'automation': matches[0]})
        return 0
    print_json({'status': 'ok', **payload})
    return 0


def automation_add_command(args: argparse.Namespace) -> int:
    from teaagent.automation_ticket import (
        build_automation_dry_run_payload,
        validate_automation_spec,
    )

    draft = AutomationSpec(
        automation_id='',
        name=args.name,
        task=args.task,
        schedule=args.schedule,
        provider=args.provider,
        model=args.model,
        permission_mode=args.permission_mode,
        context_profile=args.context_profile,
        max_iterations=args.max_iterations,
        max_tool_calls=args.max_tool_calls,
        auto_propose_skill=bool(getattr(args, 'auto_propose_skill', False)),
        selected_skills=tuple(getattr(args, 'skill', None) or ()),
        acceptance_criteria=str(getattr(args, 'acceptance_criteria', '')).strip(),
        collector_command=str(getattr(args, 'collector_command', '')).strip(),
        no_agent=bool(getattr(args, 'no_agent', False)),
    )
    if draft.no_agent and not draft.collector_command:
        print_json(
            {
                'status': 'error',
                'errors': ['no_agent requires --collector-command'],
            }
        )
        return 1
    if getattr(args, 'dry_run', False):
        payload = build_automation_dry_run_payload(
            draft, root=args.root, human=bool(getattr(args, 'human', False))
        )
        print_json(payload)
        if payload['ticket']['errors']:
            return 1
        return 0

    report = validate_automation_spec(draft, root=args.root)
    if report.errors:
        print_json(
            {'status': 'error', 'errors': report.errors, 'warnings': report.warnings}
        )
        return 1

    spec = AutomationStore(args.root).create(
        name=args.name,
        task=args.task,
        schedule=args.schedule,
        provider=args.provider,
        model=args.model,
        permission_mode=args.permission_mode,
        context_profile=args.context_profile,
        max_iterations=args.max_iterations,
        max_tool_calls=args.max_tool_calls,
        auto_propose_skill=bool(getattr(args, 'auto_propose_skill', False)),
        selected_skills=list(draft.selected_skills),
        acceptance_criteria=draft.acceptance_criteria,
        collector_command=draft.collector_command,
        no_agent=draft.no_agent,
    )
    print_json(
        {'status': 'created', 'automation': spec.to_dict(), 'warnings': report.warnings}
    )
    return 0


def automation_list_command(args: argparse.Namespace) -> int:
    specs = [spec.to_dict() for spec in AutomationStore(args.root).list()]
    print_json(specs)
    return 0


def automation_show_command(args: argparse.Namespace) -> int:
    try:
        spec = AutomationStore(args.root).show(args.automation_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(spec.to_dict())
    return 0


def automation_pause_command(args: argparse.Namespace) -> int:
    try:
        spec = AutomationStore(args.root).set_enabled(args.automation_id, False)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json({'status': 'paused', 'automation': spec.to_dict()})
    return 0


def automation_resume_command(args: argparse.Namespace) -> int:
    try:
        spec = AutomationStore(args.root).set_enabled(args.automation_id, True)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json({'status': 'resumed', 'automation': spec.to_dict()})
    return 0


def automation_delete_command(args: argparse.Namespace) -> int:
    try:
        AutomationStore(args.root).delete(args.automation_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json({'status': 'deleted', 'automation_id': args.automation_id})
    return 0


def automation_run_command(args: argparse.Namespace) -> int:
    try:
        spec = AutomationStore(args.root).show(args.automation_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    payload = _run_automation_once(args.root, spec)
    print_json(payload)
    return 0


def automation_tick_command(args: argparse.Namespace) -> int:
    payload = _automation_tick(args.root, dry_run=bool(getattr(args, 'dry_run', False)))
    print_json(payload)
    return 0


def _automation_tick(root: str, *, dry_run: bool) -> dict[str, Any]:
    store = AutomationStore(root)
    _reconcile_automation_runs(root, store)
    health = _automation_health(store)
    if dry_run:
        due = [spec.to_dict() for spec in store.due()]
        return {'status': 'dry_run', 'due': due, 'count': len(due), 'health': health}
    results: list[dict[str, Any]] = []
    with AutomationTickLock(root):
        for spec in store.due():
            results.append(_run_automation_once(root, spec))
    return {
        'status': 'ok',
        'executed': results,
        'count': len(results),
        'health': health,
    }


def automation_serve_command(args: argparse.Namespace) -> int:
    stop_requested = {'value': False}

    def _handle_signal(_sig: int, _frame: Any) -> None:
        stop_requested['value'] = True

    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    tick_count = 0
    started_at = time.monotonic()
    max_ticks = int(getattr(args, 'max_ticks', 0))
    interval = float(getattr(args, 'interval_seconds', 30.0))
    try:
        while True:
            if stop_requested['value']:
                print_json(
                    {
                        'status': 'stopped',
                        'reason': 'signal',
                        'ticks_completed': tick_count,
                    }
                )
                return 0
            payload = _automation_tick(args.root, dry_run=False)
            tick_count += 1
            print_json(
                {
                    'status': 'serve_tick',
                    'tick': tick_count,
                    'executed_count': payload.get('count', 0),
                    'uptime_seconds': round(time.monotonic() - started_at, 1),
                    'health': payload.get('health', {}),
                    'last_tick': payload,
                }
            )
            if max_ticks > 0 and tick_count >= max_ticks:
                print_json(
                    {
                        'status': 'stopped',
                        'reason': 'max_ticks',
                        'ticks_completed': tick_count,
                        'uptime_seconds': round(time.monotonic() - started_at, 1),
                    }
                )
                return 0
            time.sleep(interval)
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


def _reconcile_automation_runs(root: str, store: AutomationStore) -> None:
    from teaagent.ergonomics.background_run import BackgroundRunStore

    bg_store = BackgroundRunStore(root)
    run_store = RunStore(root)
    candidate_store = SkillCandidateStore(root)
    for spec in store.list():
        if not spec.running_background_id:
            continue
        try:
            bg = bg_store.get(spec.running_background_id)
        except FileNotFoundError:
            updated = AutomationSpec(
                **{
                    **spec.to_dict(),
                    'running_background_id': None,
                    'last_status': 'background_missing',
                }
            )
            store.update(updated)
            continue
        run_id = bg.get('run_id') if isinstance(bg.get('run_id'), str) else None
        alive = bool(bg.get('alive'))
        next_state: dict[str, Any] = {}
        if run_id:
            next_state['last_run_id'] = run_id
            try:
                heartbeat = run_store.heartbeat_for_run(run_id)
                status = str(heartbeat.get('status', 'running'))
            except FileNotFoundError:
                status = 'running'
            next_state['last_status'] = status
            if (
                spec.auto_propose_skill
                and status == 'completed'
                and spec.last_run_id != run_id
            ):
                with contextlib.suppress(FileNotFoundError, ValueError):
                    candidate_store.create_from_run(
                        run_id=run_id,
                        name=f'{spec.name}-auto',
                        description=f'Auto-proposed from automation {spec.name}',
                    )
        if not alive:
            next_state['running_background_id'] = None
        if next_state:
            store.update(AutomationSpec(**{**spec.to_dict(), **next_state}))


def _automation_health(store: AutomationStore) -> dict[str, int]:
    specs = store.list()
    enabled = [spec for spec in specs if spec.enabled]
    due_ready = store.due()
    running = [spec for spec in specs if spec.running_background_id]
    return {
        'automation_count': len(specs),
        'enabled_count': len(enabled),
        'due_count': len(due_ready),
        'running_count': len(running),
    }


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
                    'heartbeat': heartbeat,
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
                        'heartbeat': heartbeat,
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

            notify('TeaAgent', f'Run {args.run_id}: {heartbeat.get("status")}')
        return 0
    print_json(
        {
            'heartbeat': heartbeat,
            'pending_approval': pending,
            'event_count': len(store.show_run(args.run_id)),
        }
    )
    if getattr(args, 'notify', False):
        from teaagent.ergonomics.notify import notify

        notify('TeaAgent', f'Run {args.run_id}: {heartbeat.get("status")}')
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
        return 0 if ready or not getattr(args, 'human', False) else 2
    brief = build_daily_brief(
        task=args.task,
        root=args.root,
        provider=args.provider,
        model=args.model,
        permission_mode=parse_permission_mode(args.permission_mode),
        route=args.route_model,
        memory_limit=args.memory_limit,
        runs_limit=args.runs_limit,
        context_profile=args.context_profile,
    )
    if getattr(args, 'write_journal', False):
        from teaagent.ergonomics.daily_journal import write_daily_journal

        write_daily_journal(brief, root=args.root)
    from teaagent.ergonomics.whats_new import whats_new_banner

    banner = whats_new_banner(args.root)
    payload = brief.to_dict()
    if banner:
        payload['whats_new'] = banner
    if getattr(args, 'human', False):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root, title='TeaAgent daily'))
    else:
        print_json(payload)
    return 0 if brief.ready else 2


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
