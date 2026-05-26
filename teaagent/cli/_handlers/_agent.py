from __future__ import annotations

import argparse
import contextlib
import json
import signal
import sys
import time
from pathlib import Path
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
from teaagent.plan import PlanContract
from teaagent.policy import parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore, summarize_audit_events
from teaagent.runner import ApprovalHandler, ApprovalRequest, RunResult
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


def agent_run_task(args: argparse.Namespace) -> int:
    if getattr(args, 'background', False):
        return _start_background_run(args)
    try:
        task, plan_contract = _resolve_run_task(args)
    except (FileNotFoundError, ValueError) as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
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
    return _execute_agent_task(args, task, plan_contract=plan_contract)


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

    # Load scoped approvals for this specific run only
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    approval_store = ApprovalPresetStore(args.root)

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
            digest = pending.get('argument_digest')
            if not digest:
                import sys

                print(
                    f"Warning: Pending call '{pending['call_id']}' is a legacy record and "
                    f'cannot be auto-approved safely due to redacted arguments. '
                    f'Please approve explicitly with --approve-call-id {pending["call_id"]}.',
                    file=sys.stderr,
                )
            else:
                # Check if this pending call already has a valid scoped approval to avoid duplicate storage writes
                if not approval_store.check_scoped_approval(
                    run_id=args.run_id,
                    call_id=pending['call_id'],
                    tool_name=pending['tool_name'],
                    arguments=pending['arguments'],
                ):
                    approval_store.add_scoped_approval(
                        run_id=args.run_id,
                        call_id=pending['call_id'],
                        tool_name=pending['tool_name'],
                        arguments=pending['arguments'],
                        argument_digest=digest,
                    )
                auto_approved = pending['call_id']

    # Legacy Escape Hatch: keep only explicitly provided bare call IDs from the --approve-call-id CLI flag
    # for backward compatibility. We never merge database-persisted scoped approvals here as bare IDs.
    args.approve_call_id = frozenset(args.approve_call_id)

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
    plan_contract: Optional[Any] = None,
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
    merged_context_extra: dict[str, Any] = dict(initial_context_extra or {})
    if resumed_from:
        merged_context_extra['resumed_from'] = resumed_from
    if plan_contract is not None:
        merged_context_extra['plan_contract'] = plan_contract.to_dict()
    store = RunStore(args.root)
    audit = store.audit_logger()
    from teaagent.run_undo import UndoJournal

    undo_journal = UndoJournal(args.root)
    audit.add_sink(undo_journal)

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

    resolved_permission_mode = parse_permission_mode(args.permission_mode)
    approval_handler = (
        make_cli_approval_handler(
            args.root, permission_mode=resolved_permission_mode.value
        )
        if args.hitl_approval
        else None
    )
    checkpoint_store = None
    checkpoint_path = getattr(args, 'checkpoint_store', None)
    if checkpoint_path:
        from teaagent.checkpoint import SQLiteCheckpointStore

        checkpoint_store = SQLiteCheckpointStore(checkpoint_path)
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
            max_estimated_cost_cents=int(
                getattr(args, 'max_estimated_cost_cents', 0) or 0
            ),
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
        initial_context_extra=merged_context_extra or None,
    )
    store.logger_for_result(result, audit)
    if undo_journal.has_entries:
        undo_journal.save_to(store.undo_path(result.run_id))
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
    if plan_contract is not None:
        payload['plan_contract'] = plan_contract.to_dict()
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
            f'Approve destructive tool call {request.call_id} ({request.tool_name})? [y/N] ',
            end='',
            file=sys.stderr,
        )
        answer = input()
        return answer.strip().lower() in {'y', 'yes'}

    return _handler


def cli_approval_handler(request: ApprovalRequest) -> bool:
    """Default handler for cwd workspace; prefer ``make_cli_approval_handler(root)``."""
    return make_cli_approval_handler('.')(request)


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


def agent_plan_command(args: argparse.Namespace) -> int:
    from teaagent.plan import write_plan_artifact

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


def agent_undo_command(args: argparse.Namespace) -> int:
    from teaagent.run_undo import UndoJournal

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
    result = journal.restore()
    status = 'restored' if result.ok else 'partial'
    rel_undo = undo_path.resolve().relative_to(store.root).as_posix()
    payload = {
        'status': status,
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
    task: Optional[str] = None,
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
        subagent=bool(spec.requires_subagent),
        max_subagent_depth=1,
        heartbeat=0.0,
        code_analysis=False,
        context_profile=spec.context_profile,
        selected_skills=list(spec.selected_skills),
        max_estimated_cost_cents=spec.max_cost_cents,
    )
    command = build_agent_run_command(run_args, task or spec.task)
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
    from teaagent.automation_chain import (
        persist_automation_handoff,
        resolve_chained_task,
    )
    from teaagent.automation_collector import run_collector_command
    from teaagent.automation_delivery import deliver_automation_tick
    from teaagent.automation_ticket import (
        compose_self_contained_automation_task,
        validate_automation_runtime_integrity,
    )

    store = AutomationStore(root)
    integrity_errors = validate_automation_runtime_integrity(spec, root=root)
    if integrity_errors:
        updated = store.update(
            AutomationSpec(
                **{
                    **spec.to_dict(),
                    'last_status': 'integrity_failed',
                    'next_run_at': compute_next_run_at(spec.schedule),
                }
            )
        )
        deliver_automation_tick(
            root,
            updated,
            status='integrity_failed',
        )
        return {
            'automation_id': spec.automation_id,
            'name': spec.name,
            'status': 'integrity_failed',
            'errors': integrity_errors,
            'next_run_at': updated.next_run_at,
        }
    if _automation_is_running(root, spec.running_background_id):
        return {
            'automation_id': spec.automation_id,
            'name': spec.name,
            'status': 'skipped_running',
            'running_background_id': spec.running_background_id,
        }
    collector_payload: Optional[dict[str, Any]] = None
    collector_summary = ''
    if spec.collector_command.strip():
        collector_payload = run_collector_command(
            spec.collector_command, root=root
        ).to_dict()
        collector_summary = str(collector_payload.get('summary', '') or '')
        persist_automation_handoff(
            root,
            spec,
            collector_summary=collector_summary,
            summary=collector_summary,
        )
        if (
            collector_payload.get('timed_out')
            or int(collector_payload['exit_code']) != 0
        ):
            updated = store.update(
                AutomationSpec(
                    **{
                        **spec.to_dict(),
                        'last_status': 'collector_failed',
                        'next_run_at': compute_next_run_at(spec.schedule),
                    }
                )
            )
            deliver_automation_tick(
                root,
                updated,
                status='collector_failed',
                collector=collector_payload,
            )
            return {
                'automation_id': spec.automation_id,
                'name': spec.name,
                'status': 'collector_failed',
                'collector': collector_payload,
                'next_run_at': updated.next_run_at,
            }
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
            deliver_automation_tick(
                root,
                updated,
                status='skipped_no_wake',
                collector=collector_payload,
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
            deliver_automation_tick(
                root,
                updated,
                status=status,
                collector=collector_payload,
            )
            return {
                'automation_id': spec.automation_id,
                'name': spec.name,
                'status': status,
                'collector': collector_payload,
                'next_run_at': updated.next_run_at,
            }
    agent_task, _handoff = resolve_chained_task(
        root, spec, collector_summary=collector_summary
    )
    agent_task = compose_self_contained_automation_task(
        spec,
        task=agent_task,
        collector_summary=collector_summary,
    )
    record = _start_automation_background_run(root=root, spec=spec, task=agent_task)
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
    if _handoff is not None:
        result['context_from_handoff'] = _handoff.to_dict()
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


def _automation_draft_from_args(
    args: argparse.Namespace,
    *,
    name: str,
    task: str,
    schedule: str,
) -> AutomationSpec:
    from teaagent.automation_collector import compute_collector_command_digest
    from teaagent.automation_ticket import compute_automation_provenance_digest

    collector_digest, _collector_errors = compute_collector_command_digest(
        str(getattr(args, 'collector_command', '')).strip(),
        root=getattr(args, 'root', '.'),
    )

    draft = AutomationSpec(
        automation_id='',
        name=name,
        task=task,
        schedule=schedule,
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
        collector_command_digest=collector_digest,
        no_agent=bool(getattr(args, 'no_agent', False)),
        allowed_toolsets=tuple(getattr(args, 'allowed_toolset', None) or ()),
        requires_subagent=bool(getattr(args, 'requires_subagent', False)),
        max_cost_cents=int(getattr(args, 'max_cost_cents', 0) or 0),
        max_runtime_seconds=int(getattr(args, 'max_runtime_seconds', 0) or 0),
        delivery=str(getattr(args, 'delivery', 'background_log')),
        context_from=str(getattr(args, 'context_from', '')).strip(),
    )
    digest = compute_automation_provenance_digest(draft)
    return AutomationSpec(**{**draft.to_dict(), 'provenance_digest': digest})


def _automation_create_kwargs_from_args(
    args: argparse.Namespace, draft: AutomationSpec
) -> dict[str, Any]:
    return {
        'name': args.name,
        'task': args.task,
        'schedule': args.schedule,
        'provider': args.provider,
        'model': args.model,
        'permission_mode': args.permission_mode,
        'context_profile': args.context_profile,
        'max_iterations': args.max_iterations,
        'max_tool_calls': args.max_tool_calls,
        'auto_propose_skill': bool(getattr(args, 'auto_propose_skill', False)),
        'selected_skills': list(draft.selected_skills),
        'acceptance_criteria': draft.acceptance_criteria,
        'collector_command': draft.collector_command,
        'collector_command_digest': draft.collector_command_digest,
        'no_agent': draft.no_agent,
        'allowed_toolsets': list(draft.allowed_toolsets),
        'requires_subagent': draft.requires_subagent,
        'max_cost_cents': draft.max_cost_cents,
        'max_runtime_seconds': draft.max_runtime_seconds,
        'delivery': draft.delivery,
        'context_from': draft.context_from,
        'provenance_digest': draft.provenance_digest,
    }


def automation_template_command(args: argparse.Namespace) -> int:
    from teaagent.automation_templates import get_automation_template
    from teaagent.automation_ticket import build_automation_dry_run_payload

    if not getattr(args, 'dry_run', False):
        print_json(
            {
                'status': 'error',
                'message': 'automation template requires --dry-run (no model invocation)',
            }
        )
        return 1
    try:
        template = get_automation_template(args.template_name)
    except KeyError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    spec = template.to_spec()
    payload = build_automation_dry_run_payload(
        spec,
        root=args.root,
        human=bool(getattr(args, 'human', False)),
        template=template.name,
    )
    print_json(payload)
    if payload['ticket']['errors']:
        return 1
    return 0


def automation_add_command(args: argparse.Namespace) -> int:
    from teaagent.automation_ticket import (
        automation_provenance_payload,
        build_automation_dry_run_payload,
        validate_automation_spec,
    )

    draft = _automation_draft_from_args(
        args, name=args.name, task=args.task, schedule=args.schedule
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

    from teaagent.provenance_gate import (
        PersistenceSubstrate,
        evaluate_persistent_write,
        parse_source_kind,
    )

    store = AutomationStore(args.root)
    source_kind = parse_source_kind(getattr(args, 'write_source', None))
    gate = evaluate_persistent_write(
        substrate=PersistenceSubstrate.AUTOMATION,
        payload=automation_provenance_payload(draft),
        source_kind=source_kind,
        attested=bool(getattr(args, 'i_attest_untrusted_write', False)),
    )
    create_kwargs = _automation_create_kwargs_from_args(args, draft)
    if gate.quarantine:
        spec = store.draft(**create_kwargs, enabled=False)
        store.create_quarantined(spec, provenance=gate.to_dict())
        print_json(
            {
                'status': 'quarantined',
                'automation': spec.to_dict(),
                'provenance': gate.to_dict(),
                'warnings': report.warnings,
            }
        )
        return 0

    spec = store.create(**create_kwargs)
    print_json(
        {
            'status': 'created',
            'automation': spec.to_dict(),
            'provenance': gate.to_dict(),
            'warnings': report.warnings,
        }
    )
    return 0


def automation_list_command(args: argparse.Namespace) -> int:
    store = AutomationStore(args.root)
    if getattr(args, 'quarantined', False):
        print_json(store.list_quarantined())
        return 0
    specs = [spec.to_dict() for spec in store.list()]
    print_json(specs)
    return 0


def automation_promote_command(args: argparse.Namespace) -> int:
    store = AutomationStore(args.root)
    try:
        spec = store.promote_quarantined(
            args.automation_id,
            attested=bool(getattr(args, 'i_attest_untrusted_write', False)),
        )
    except (FileNotFoundError, ValueError) as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json({'status': 'promoted', 'automation': spec.to_dict()})
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
    from teaagent.automation_chain import persist_automation_handoff
    from teaagent.automation_delivery import deliver_automation_tick
    from teaagent.automation_limits import cost_cap_exceeded, enforce_runtime_cap
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
        runtime_capped = enforce_runtime_cap(
            bg, max_runtime_seconds=spec.max_runtime_seconds
        )
        if runtime_capped:
            bg = bg_store.get(spec.running_background_id)
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
            if runtime_capped and not alive:
                next_state['last_status'] = 'runtime_cap_exceeded'
            elif (
                not alive
                and status == 'completed'
                and cost_cap_exceeded(root, spec, run_id=run_id)
            ):
                next_state['last_status'] = 'cost_cap_exceeded'
            else:
                next_state['last_status'] = status
            if (
                spec.auto_propose_skill
                and next_state['last_status'] == 'completed'
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
        refreshed = spec
        if next_state:
            refreshed = store.update(AutomationSpec(**{**spec.to_dict(), **next_state}))
        log_tail = ''
        log_path = bg.get('log_path')
        if isinstance(log_path, str):
            path = Path(log_path)
            if path.is_file():
                lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
                log_tail = '\n'.join(lines[-20:])
        persist_automation_handoff(
            root,
            refreshed,
            log_tail=log_tail,
            summary=str(refreshed.last_status or ''),
        )
        if not alive:
            deliver_automation_tick(
                root,
                refreshed,
                status=str(refreshed.last_status or 'completed'),
                log_tail=log_tail,
                run_id=run_id,
            )


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


def agent_subagent_review_list_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import list_subagent_reviews

    print_json(
        {
            'status': 'ok',
            'reviews': list_subagent_reviews(
                args.root, parent_run_id=getattr(args, 'parent_run_id', None)
            ),
        }
    )
    return 0


def agent_subagent_review_show_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import load_subagent_review

    try:
        review = load_subagent_review(
            args.root,
            args.review_id,
            parent_run_id=getattr(args, 'parent_run_id', None),
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json({'status': 'ok', 'review': review})
    return 0


def agent_subagent_review_check_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import check_subagent_review

    try:
        payload = check_subagent_review(
            args.root,
            args.review_id,
            parent_run_id=getattr(args, 'parent_run_id', None),
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(payload)
    return 0 if payload['ok'] else 2


def agent_subagent_review_apply_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import apply_subagent_review

    try:
        payload = apply_subagent_review(
            args.root,
            args.review_id,
            parent_run_id=getattr(args, 'parent_run_id', None),
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(payload)
    return 0 if payload['ok'] else 2


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
