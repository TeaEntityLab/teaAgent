from __future__ import annotations

import argparse
import contextlib
import signal
import time
from pathlib import Path
from typing import Any, Optional

from teaagent.automations import (
    AutomationSpec,
    AutomationStore,
    AutomationTickLock,
    compute_next_run_at,
)
from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.run_store import RunStore
from teaagent.skill_candidates import SkillCandidateStore


def _start_automation_background_run(
    *,
    root: str,
    spec: AutomationSpec,
    task: Optional[str] = None,
) -> dict[str, Any]:
    from teaagent.ergonomics.background_run import (
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
    record = (
        AgentExecutionFactory(root)
        .create_background_run_store()
        .start(command, label=f'automation:{spec.automation_id}:{spec.name}')
    )
    return record.to_dict()


def _automation_is_running(root: str, background_id: Optional[str]) -> bool:
    if not background_id:
        return False
    try:
        row = (
            AgentExecutionFactory(root).create_background_run_store().get(background_id)
        )
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
    if payload.get('ticket', {}).get('errors'):
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
    store = AutomationStore(args.root, readonly=True)
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
        spec = AutomationStore(args.root, readonly=True).show(args.automation_id)
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


def _resolve_automation_status(
    bg: dict[str, Any],
    spec: AutomationSpec,
    root: str,
    run_store: RunStore,
    candidate_store: Any,
    runtime_capped: bool,
) -> dict[str, Any]:
    from teaagent.automation_limits import cost_cap_exceeded

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
        _maybe_auto_propose_skill(spec, run_id, next_state, candidate_store)
    if not alive:
        next_state['running_background_id'] = None
    return next_state


def _maybe_auto_propose_skill(
    spec: AutomationSpec,
    run_id: str,
    next_state: dict[str, Any],
    candidate_store: Any,
) -> None:
    if (
        spec.auto_propose_skill
        and next_state.get('last_status') == 'completed'
        and spec.last_run_id != run_id
    ):
        with contextlib.suppress(FileNotFoundError, ValueError):
            candidate_store.create_from_run(
                run_id=run_id,
                name=f'{spec.name}-auto',
                description=f'Auto-proposed from automation {spec.name}',
            )


def _deliver_handoff(
    root: str,
    spec: AutomationSpec,
    bg: dict[str, Any],
    alive: bool,
    next_state: dict[str, Any],
    refreshed: AutomationSpec,
) -> None:
    from teaagent.automation_chain import persist_automation_handoff
    from teaagent.automation_delivery import deliver_automation_tick

    log_path = bg.get('log_path')
    log_tail = ''
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
            run_id=next_state.get('last_run_id'),
        )


def _reconcile_automation_runs(root: str, store: AutomationStore) -> None:
    from teaagent.automation_limits import enforce_runtime_cap

    bg_store = AgentExecutionFactory(root).create_background_run_store()
    run_store = AgentExecutionFactory(root).create_run_store()
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
        alive = bool(bg.get('alive'))
        next_state = _resolve_automation_status(
            bg, spec, root, run_store, candidate_store, runtime_capped
        )
        refreshed = spec
        if next_state:
            refreshed = store.update(AutomationSpec(**{**spec.to_dict(), **next_state}))
        _deliver_handoff(root, spec, bg, alive, next_state, refreshed)


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
