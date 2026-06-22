from __future__ import annotations

import argparse
import atexit
import logging
import os as _os
import signal
import sys
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.approval import parse_permission_mode
from teaagent.chat_agent import run_chat_agent
from teaagent.cli._formatting import format_error_block
from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.code_analysis import CodeAnalysisConfig
from teaagent.ergonomics.cli_output import wants_human_cli
from teaagent.intent import build_task_spec, clarify_task
from teaagent.model_routing import route_model
from teaagent.run_store import safe_run_id, summarize_audit_events
from teaagent.types import PermissionMode

from .config import (
    _derive_policy_source,
    _parse_approve_scoped,
    _require_plan_gate,
    _resolve_selected_skills,
    _resolve_validation_profile,
    _run_post_validation,
    _save_git_sandbox_consent,
    warn_if_approve_call_id_used,
)
from .output import (
    _display_recovery_guidance,
    _emit_readiness_payload,
    _emit_run_completion_output,
    show_interactive_diff,
)
from .sandbox_resolution import (
    record_git_sandbox_started,
    resolve_git_sandbox_after_run,
)
from .task import _prepare_task, _resolve_run_task

logger = logging.getLogger(__name__)


def _start_background_run(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import (
        build_agent_run_command,
    )

    factory = AgentExecutionFactory(args.root)
    run_store = factory.create_run_store(readonly=True)
    root_path = Path(args.root).resolve()

    # Check both positional arguments for run/suspension ID patterns.
    # When --background is used without a provider (e.g. "agent run --background <id>"),
    # the <id> lands in args.provider. When a provider is specified
    # (e.g. "agent run gpt --background <id>"), the <id> lands in args.task.
    candidates = []
    for raw in (getattr(args, 'provider', None), getattr(args, 'task', None)):
        if raw is not None:
            stripped = str(raw).strip()
            if stripped:
                candidates.append(stripped)

    for candidate in candidates:
        run_path = run_store.run_path(candidate)
        suspension_path = (
            root_path / '.teaagent' / f'suspension-{safe_run_id(candidate)}.json'
        )
        if run_path.is_file():
            print(
                format_error_block(
                    'Error',
                    f"'{candidate}' looks like an existing run id. "
                    f'Use `teaagent agent resume {candidate}` or '
                    f'`teaagent agent interactive-review {candidate}` instead. '
                    '--background launches a new detached task; it is not for resuming.',
                    category='BACKGROUND',
                ),
                file=sys.stderr,
            )
            return 2
        if suspension_path.is_file():
            print(
                format_error_block(
                    'Error',
                    f"'{candidate}' looks like a suspension id. "
                    f'Use `teaagent agent interactive-review {candidate}` '
                    'to inspect it; true resume is not yet available for REPL '
                    'suspensions.',
                    category='BACKGROUND',
                ),
                file=sys.stderr,
            )
            return 2

    task = _prepare_task(args, args.task)
    command = build_agent_run_command(args, task)
    record = factory.create_background_run_store().start(command)
    payload = record.to_dict()
    payload['status'] = 'background_started'
    payload['attach'] = (
        f'teaagent agent attach <run_id> --follow --root {args.root} '
        '(run_id appears in log when the worker starts)'
    )
    print_json(payload)
    return 0


def agent_run_task(args: argparse.Namespace) -> int:
    if getattr(args, 'background', False):
        return _start_background_run(args)
    try:
        task, plan_contract = _resolve_run_task(args)
    except (FileNotFoundError, ValueError) as exc:
        print(
            format_error_block(
                'Error',
                str(exc),
                hint='provider comes first: `teaagent agent run PROVIDER [task]`',
            ),
            file=sys.stderr,
        )
        return 1
    run_id_candidate = (getattr(args, 'task', None) or '').strip()
    if run_id_candidate:
        from teaagent.run_store import RunStore

        store = RunStore(Path(args.root))
        if store.run_path(run_id_candidate).is_file():
            print(
                format_error_block(
                    'Error',
                    f"'{run_id_candidate}' is an existing run id, not a task description.",
                    hint=(
                        f'Use `teaagent agent resume {run_id_candidate}` or '
                        f'`teaagent agent interactive-review {run_id_candidate}`. '
                        'Do not pass a run id as the task text.'
                    ),
                    category='RUN_ID',
                ),
                file=sys.stderr,
            )
            return 2
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
        return 0 if ready or not wants_human_cli(args) else 2
    return _execute_agent_task(args, task, plan_contract=plan_contract)


def _execute_agent_task(  # noqa: C901
    args: argparse.Namespace,
    task: str,
    *,
    resumed_from: Optional[str] = None,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    initial_context_extra: Optional[dict[str, Any]] = None,
    auto_approved_call_id: Optional[str] = None,
    plan_contract: Optional[Any] = None,
) -> int:
    # First-run orientation (shown once per workspace)
    from teaagent.cli._handlers._misc import handle_first_run

    # Suppress welcome message in test environment
    quiet = getattr(args, 'quiet', False) or _os.environ.get('TEAAGENT_QUIET') == '1'
    handle_first_run(Path(args.root), quiet=quiet)
    # Handle parallel experiments
    parallel_value = getattr(args, 'parallel', None)
    if parallel_value:
        if isinstance(parallel_value, int):
            mode = parse_permission_mode(args.permission_mode)
            if mode != PermissionMode.READ_ONLY:
                print(
                    format_error_block(
                        'Error',
                        'Numeric --parallel requires read-only permission mode '
                        'for safe parallel analysis branches.',
                        category='PARALLEL',
                    ),
                    file=sys.stderr,
                )
                return 2
            parallel_options = ','.join(
                f'approach-{index + 1}' for index in range(parallel_value)
            )
        else:
            parallel_options = str(parallel_value)
        from .experiment import _execute_parallel_experiment

        return _execute_parallel_experiment(args, task, parallel_options)

    task_spec = None
    if args.clarify:
        clarification = clarify_task(task)
        if clarification.needs_clarification:
            clarify_json = getattr(args, 'clarify_json', False)
            if clarify_json or not sys.stdin.isatty():
                print_json(
                    {
                        'status': 'needs_clarification',
                        'clarification': clarification.to_dict(),
                    }
                )
                return 2
            if clarification.question:
                print(clarification.question)
            answer = input('> ')
            if answer.strip():
                task = answer.strip()
        task_spec = build_task_spec(task, clarification)

    routing = (
        route_model(task, provider=args.provider, model=args.model)
        if args.route_model
        else None
    )
    selected_model = routing.model if routing else args.model
    adapter = args._adapter_factory(args.provider, model=selected_model)
    merged_context_extra: dict[str, Any] = dict(initial_context_extra or {})
    merged_context_extra.setdefault('provider', args.provider)
    if selected_model:
        merged_context_extra.setdefault('model', selected_model)
    if resumed_from:
        merged_context_extra['resumed_from'] = resumed_from
    if plan_contract is not None:
        merged_context_extra['plan_contract'] = plan_contract.to_dict()
    # The plan contract provides the task and scope, but permission mode is always
    # taken from the command-line argument to allow the user to override the plan's
    # suggested mode for the actual execution.
    gate_exit = _require_plan_gate(args, plan_contract)
    if gate_exit is not None:
        return gate_exit
    factory = AgentExecutionFactory(args.root)
    store = factory.create_run_store()
    audit = factory.create_audit_logger(store)

    if routing is not None:
        _policy_source = _derive_policy_source(routing.reason)
        _fallback_used = routing.model is None
        audit.record(
            'model_route',
            run_id='pending',
            requested_provider=args.provider,
            requested_model=args.model or '',
            resolved_provider=routing.provider,
            resolved_model=routing.model or '',
            role=routing.category,
            routing_reason=routing.reason,
            policy_source=_policy_source,
            estimated_cost_cents=0.0,
            actual_cost_cents=0.0,
            fallback_used=_fallback_used,
        )

    from teaagent.scratchpad import Scratchpad

    scratchpad = Scratchpad(Path(args.root))

    _sp_state: dict[str, object] = {
        'written': False,
    }

    def _write_scratchpad_on_exit() -> None:
        if _sp_state['written']:
            return
        try:
            scratchpad.write(
                goal=task,
                progress='Session interrupted before completion.',
                open_questions=[],
                next_step='Resume from previous session.',
            )
            _sp_state['written'] = True
        except (OSError, IOError) as exc:
            import logging

            logging.getLogger(__name__).warning('Scratchpad write error: %s', exc)

    atexit.register(_write_scratchpad_on_exit)

    previous = signal.signal(
        signal.SIGINT, lambda sig, frame: _write_scratchpad_on_exit()
    )
    _ = previous  # Signal handler for cleanup; intentionally not restored

    # Resume offer on session start
    if scratchpad.exists() and not resumed_from:
        content = scratchpad.read()
        if content:
            is_interactive = sys.stdin.isatty()
            if is_interactive:
                print(
                    '\nFound scratchpad from previous session.',
                    file=sys.stderr,
                )
                print(
                    f'Last goal: {content.get("last_goal", "(none)")}',
                    file=sys.stderr,
                )
                progress = content.get('progress', '')
                if progress:
                    print(f'Progress: {progress}', file=sys.stderr)
                print('Resume? (y/n): ', end='', file=sys.stderr)
                choice = input().strip().lower()
                if choice in ('y', 'yes'):
                    resume_prompt = scratchpad.resume_prompt()
                    if resume_prompt:
                        merged_context_extra['scratchpad_resume'] = resume_prompt
                        task = f'{task}\n\n{resume_prompt}'
                else:
                    scratchpad.clear()
            else:
                scratchpad.clear()

    # Pre-generate run_id so sandbox branch name matches the final run record.
    pending_run_id = uuid4().hex

    git_sandbox = factory.create_git_sandbox(run_id=pending_run_id)
    git_sandbox_available = git_sandbox.is_available()
    auto_stash = getattr(args, 'git_sandbox_auto_stash', False)

    # Safe sandbox consent prompting
    if git_sandbox_available:
        from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

        defaults = load_workspace_defaults(args.root)
        consent = defaults.get('git_sandbox_consent', 'prompt')
        is_interactive = sys.stdin.isatty()

        # Option A: Auto-enable without prompt (always consent or non-interactive)
        if consent == 'always' or not is_interactive:
            print(
                '[TeaAgent] Git repository detected. Safe git sandbox auto-enabled.',
                file=sys.stderr,
            )
            sandbox_result = git_sandbox.start(auto_stash=auto_stash)
            if sandbox_result.success:
                record_git_sandbox_started(
                    audit,
                    pending_run_id,
                    git_sandbox,
                    auto_stash=auto_stash,
                    success=True,
                )
            else:
                print(
                    f'[TeaAgent WARNING] Git sandbox initialization failed: {sandbox_result.error}',
                    file=sys.stderr,
                )
                record_git_sandbox_started(
                    audit,
                    pending_run_id,
                    git_sandbox,
                    auto_stash=auto_stash,
                    success=False,
                    error=sandbox_result.error,
                )
                git_sandbox_available = False
        # Option B: Interactive prompting
        else:
            print(
                '[TeaAgent] Git repository detected. Would you like to run in a safe sandbox branch? [Y/n/always]: ',
                end='',
                file=sys.stderr,
            )
            choice = input().strip().lower()

            if choice in ('always', 'a'):
                _save_git_sandbox_consent(args.root, 'always')
                print(
                    '[TeaAgent] Preference saved. Safe git sandbox will be auto-enabled for this project.',
                    file=sys.stderr,
                )
                sandbox_result = git_sandbox.start(auto_stash=auto_stash)
                if sandbox_result.success:
                    record_git_sandbox_started(
                        audit,
                        pending_run_id,
                        git_sandbox,
                        auto_stash=auto_stash,
                        success=True,
                    )
                else:
                    print(
                        f'[TeaAgent WARNING] Git sandbox initialization failed: {sandbox_result.error}',
                        file=sys.stderr,
                    )
                    record_git_sandbox_started(
                        audit,
                        pending_run_id,
                        git_sandbox,
                        auto_stash=auto_stash,
                        success=False,
                        error=sandbox_result.error,
                    )
                    git_sandbox_available = False
            elif choice in ('yes', 'y', ''):
                sandbox_result = git_sandbox.start(auto_stash=auto_stash)
                if sandbox_result.success:
                    record_git_sandbox_started(
                        audit,
                        pending_run_id,
                        git_sandbox,
                        auto_stash=auto_stash,
                        success=True,
                    )
                else:
                    print(
                        f'[TeaAgent WARNING] Git sandbox initialization failed: {sandbox_result.error}',
                        file=sys.stderr,
                    )
                    record_git_sandbox_started(
                        audit,
                        pending_run_id,
                        git_sandbox,
                        auto_stash=auto_stash,
                        success=False,
                        error=sandbox_result.error,
                    )
                    git_sandbox_available = False
            else:
                print(
                    '[TeaAgent] Sandbox declined. Running in local workspace directly.',
                    file=sys.stderr,
                )
                git_sandbox_available = False

    undo_journal = factory.create_undo_journal()
    audit.add_sink(undo_journal)

    # Add git transaction sink if sandbox is active
    git_transaction_sink = None
    if git_sandbox_available:
        git_transaction_sink = factory.create_git_transaction_sink(git_sandbox)
        audit.add_sink(git_transaction_sink)

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
            adapter = args._adapter_factory(
                args.provider,
                model=selected_model,
                transport=TracingHTTPTransport(adapter.transport, tracer),
            )
        except Exception as exc:
            print(f'Telemetry setup failed: {exc}', file=sys.stderr)

    from .approval import (
        make_cli_approval_handler,
        make_cli_budget_prompt_handler,
    )

    resolved_permission_mode = parse_permission_mode(args.permission_mode)
    approval_handler = (
        make_cli_approval_handler(
            args.root, permission_mode=resolved_permission_mode.value
        )
        if args.hitl_approval
        else None
    )
    budget_prompt_handler = None
    if (
        sys.stdin.isatty()
        and not getattr(args, 'background', False)
        and not getattr(args, 'json_stream', False)
    ):
        budget_prompt_handler = make_cli_budget_prompt_handler()
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
    max_estimated_cost_cents = getattr(args, 'max_estimated_cost_cents', 500)
    approved_payload_digests = _parse_approve_scoped(
        getattr(args, 'approve_scoped', [])
    )
    warn_if_approve_call_id_used(args)
    config = factory.create_chat_agent_config(
        max_iterations=args.max_iterations,
        max_tool_calls=args.max_tool_calls,
        max_estimated_cost_cents=max_estimated_cost_cents,
        allow_destructive=args.allow_destructive,
        model=selected_model,
        permission_mode=resolved_permission_mode,
        # Call-id preapproval was removed (G-P2-2); the flag is inert and only
        # surfaces a deprecation notice pointing to --approve-scoped.
        approved_call_ids=frozenset(),
        approved_payload_digests=approved_payload_digests,
        enable_subagent=args.subagent,
        max_subagent_depth=args.max_subagent_depth,
        heartbeat_seconds=args.heartbeat,
        approval_handler=approval_handler,
        budget_prompt_handler=budget_prompt_handler,
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
        require_plan=getattr(args, 'require_plan', False),
        skip_plan_check=getattr(args, 'skip_plan_check', False),
        validation_profile=_resolve_validation_profile(args),
    )
    from teaagent.provider_fallback import maybe_wrap_adapter_with_fallback

    adapter = maybe_wrap_adapter_with_fallback(
        adapter,
        root=args.root,
        primary_provider=args.provider,
        primary_model=selected_model,
        audit=audit,
        run_id=pending_run_id,
        adapter_factory=args._adapter_factory,
    )
    result = run_chat_agent(
        config,
        task,
        adapter=adapter,
        audit=audit,
        task_spec=task_spec,
        initial_observations=initial_observations,
        initial_context_extra=merged_context_extra or None,
        run_id=pending_run_id,
    )
    store.logger_for_result(result, audit)
    if undo_journal.has_entries:
        undo_journal.save_to(store.undo_path(result.run_id))

    if 'scratchpad' in dir():
        _sp_state['written'] = True
        error_msg = result.error_message or ''
        if result.status == 'completed':
            final_answer = (
                result.final_answer.content
                if result.final_answer
                else 'Task completed.'
            )
            scratchpad.write(
                goal=task,
                progress=f'Completed: {final_answer[:500]}',
                open_questions=[],
                next_step='',
                session_id=result.run_id,
            )
        else:
            scratchpad.write(
                goal=task,
                progress=f'Ended ({result.status})'
                + (f': {error_msg[:200]}' if error_msg else ''),
                open_questions=[],
                next_step='Review errors and retry.',
                session_id=result.run_id,
            )

    validation_profile = _resolve_validation_profile(args)
    if validation_profile and result.status == 'completed':
        validation_exit = _run_post_validation(
            args, result=result, store=store, profile=validation_profile
        )
        if validation_exit != 0:
            return validation_exit

    if git_sandbox_available:
        resolve_git_sandbox_after_run(
            audit=audit,
            run_id=result.run_id,
            sandbox=git_sandbox,
            args=args,
            result=result,
            show_interactive_diff=show_interactive_diff,
        )

    if _telemetry_sink is not None:
        from contextlib import suppress

        with suppress(Exception):
            _telemetry_sink.force_flush()
    events = store.show_run(result.run_id)
    from .approval import run_result_payload

    payload = run_result_payload(
        result,
        routing=routing.to_dict() if routing else None,
        audit_summary=summarize_audit_events(events),
        permission_mode=resolved_permission_mode.value,
    )
    if not getattr(args, 'no_summary', False):
        from teaagent.ergonomics.run_summary import summarize_run
        from teaagent.run_evidence import build_run_evidence_bundle

        payload['run_summary'] = summarize_run(
            root=args.root,
            run_id=result.run_id,
            events=events,
            cost_cents=result.cost_cents,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            budget_cap_cents=config.max_estimated_cost_cents,
        )
        # Surface run evidence bundle when available (commands, tests, approvals, gaps)
        try:
            evidence = build_run_evidence_bundle(args.root, result.run_id)
            if evidence.commands_run or evidence.tests or evidence.approvals:
                payload['run_evidence'] = evidence.to_dict()
        except Exception:
            logger.warning('Failed to build run evidence bundle', exc_info=True)
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
    _emit_run_completion_output(
        args,
        store=store,
        run_id=result.run_id,
        payload=payload,
    )
    if getattr(args, 'notify', False):
        from teaagent.ergonomics.notify import notify

        notify('TeaAgent', f'Run {result.run_id} {result.status}')

    # Display recovery guidance for failed or partial success runs
    if result.status != 'completed' and not getattr(args, 'json_stream', False):
        _display_recovery_guidance(result, args, store)

    return 0 if result.status == 'completed' else 1
