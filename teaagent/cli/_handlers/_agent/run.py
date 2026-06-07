from __future__ import annotations

import argparse
import json
import logging
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.cli._output import print_json
from teaagent.code_analysis import CodeAnalysisConfig
from teaagent.intent import build_task_spec, clarify_task
from teaagent.model_routing import route_model
from teaagent.policy import PermissionMode, parse_permission_mode
from teaagent.run_store import RunStore, safe_run_id, summarize_audit_events
from teaagent.runner import RunResult

logger = logging.getLogger(__name__)

# Constants for pagination and display limits
DEFAULT_DIFF_PREVIEW_LINES = 30
DEFAULT_PAGINATION_LINES = 50


def _derive_policy_source(routing_reason: str) -> str:
    """Derive the policy source from a routing reason string."""
    lower = routing_reason.lower()
    if 'explicit' in lower:
        return 'explicit_override'
    if 'complexity' in lower:
        return 'complexity'
    return 'category'


def _display_recovery_guidance(
    result: RunResult,
    args: argparse.Namespace,
    store: RunStore,
) -> None:
    """Display recovery guidance for failed or partial success runs.

    Args:
        result: RunResult from the failed run
        args: CLI arguments
        store: RunStore for accessing audit logs
    """
    from teaagent.guided_recovery import (
        FailureAnalyzer,
        RecoveryAdviceFormatter,
        RecoverySelector,
    )
    from teaagent.run_undo import UndoJournal

    # Load audit log if available
    audit_path = store.run_path(result.run_id)
    from teaagent.audit import AuditLogger

    audit = AuditLogger(path=audit_path) if audit_path.is_file() else None

    # Load undo journal if available
    undo_journal = None
    undo_path = store.undo_path(result.run_id)
    if undo_path.is_file():
        undo_journal = UndoJournal(root=args.root, path=undo_path)

    # Analyze failure
    analyzer = FailureAnalyzer(audit_logger=audit)
    failure = analyzer.classify(result)

    # Select recovery strategy
    selector = RecoverySelector(undo_journal=undo_journal)
    advice = selector.select(failure)

    # Format and display advice
    formatter = RecoveryAdviceFormatter()
    formatted_advice = formatter.format(advice, run_id=result.run_id)

    print('\n' + formatted_advice, file=sys.stderr)


def _resolve_selected_skills(args: argparse.Namespace) -> Optional[frozenset[str]]:
    """Resolve selected skills from args, returning frozenset or None.

    Returns:
        - Empty frozenset if no_auto_skills is set
        - Frozenset of skill names if provided
        - None otherwise (to trigger auto-selection)
    """
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
) -> tuple[str, Optional[Any]]:
    from teaagent.plan import load_plan_contract

    plan_contract = None
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
        try:
            config = json.loads(json_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            print(f'Warning: Failed to read configuration: {exc}', file=sys.stderr)
            config = {}
    else:
        config = {}
    config['git_sandbox_consent'] = value
    try:
        json_path.write_text(
            json.dumps(config, sort_keys=True, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        print(f'Warning: Failed to save configuration: {exc}', file=sys.stderr)


def _resolve_validation_profile(args: argparse.Namespace) -> Optional[str]:
    if getattr(args, 'no_validate', False):
        return None
    if getattr(args, 'validate', False):
        return getattr(args, 'validation_profile', None) or 'standard'
    return None


def _require_plan_gate(
    args: argparse.Namespace, plan_contract: Optional[Any]
) -> Optional[int]:
    # Strict plan-before-write enforcement for workspace-write mode (user-approved)
    mode = parse_permission_mode(args.permission_mode)
    if mode == PermissionMode.READ_ONLY:
        return None

    # Check if strict plan enforcement is enabled (default for workspace-write)
    require_plan = getattr(args, 'require_plan', False)
    skip_plan_check = getattr(args, 'skip_plan_check', False)

    # If user explicitly skips plan check, allow it (with warning logged elsewhere)
    if skip_plan_check:
        return None

    # For workspace-write mode, enforce plan requirement by default
    if mode == PermissionMode.WORKSPACE_WRITE and not require_plan:
        # Auto-enable require_plan for workspace-write mode unless explicitly skipped
        require_plan = True

    if not require_plan:
        return None

    if plan_contract is not None:
        return None
    print_json(
        {
            'status': 'error',
            'message': (
                'Plan-before-write enforcement requires a bound plan. Run `teaagent plan` then '
                '`teaagent run --from-plan .teaagent/plans/<file>.md --require-plan`. '
                'Use --skip-plan-check to override (not recommended).'
            ),
        }
    )
    return 2


def _run_post_validation(
    args: argparse.Namespace,
    *,
    result: RunResult,
    store: RunStore,
    profile: str,
) -> int:
    from teaagent.audit import AuditLogger
    from teaagent.validation.profiles import run_profile_validation

    report = run_profile_validation(args.root, profile)  # type: ignore[arg-type]
    path = store.run_path(result.run_id)
    if path.is_file():
        audit = AuditLogger(path=path)
        audit.record('validation_started', result.run_id, profile=profile)
        audit.record(
            'validation_finished',
            result.run_id,
            passed=report.passed,
            report=report.to_dict(),
        )
    payload = {'validation': report.to_dict(), 'run_id': result.run_id}
    print_json(payload)
    return 0 if report.passed else 1


def show_interactive_diff(root: str | Path, sandbox_branch: str) -> bool:
    """Show interactive diff before merge prompt.

    Args:
        root: The workspace root directory
        sandbox_branch: The sandbox branch name

    Returns:
        True if user wants to proceed, False to cancel
    """
    from pathlib import Path

    root_path = Path(root).resolve()

    print('\n=== Sandbox Merge Preview ===')
    print(f'Branch: {sandbox_branch}')
    print()

    # Get diff summary
    try:
        # Get list of changed files
        result = subprocess.run(
            ['git', 'diff', '--stat', f'{sandbox_branch}'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            print('Changed files:')
            print(result.stdout)
        else:
            print('No changes detected in sandbox branch.')
            return True

        # Ask if user wants to see detailed diff
        print('\nView detailed diff? [Y/n]: ', end='')
        choice = input().strip().lower()

        if choice in ('n', 'no'):
            return True

        # Show detailed diff with color
        print('\n=== Detailed Changes ===')
        result = subprocess.run(
            ['git', 'diff', '--color=always', f'{sandbox_branch}'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            # Paginate output if it's long
            lines = result.stdout.split('\n')
            if len(lines) > DEFAULT_PAGINATION_LINES:
                # Show first N lines
                print('\n'.join(lines[:DEFAULT_DIFF_PREVIEW_LINES]))
                print(f'\n... ({len(lines) - DEFAULT_DIFF_PREVIEW_LINES} more lines)')
                print('Press Enter to see more, or q to quit: ', end='')
                more = input().strip().lower()
                if more != 'q':
                    print('\n'.join(lines[30:]))
            else:
                print(result.stdout)
        else:
            print('No detailed changes available.')

        print('\n=== End of Diff ===')

    except FileNotFoundError:
        print('[TeaAgent] Git not found in PATH')
        return True
    except Exception as exc:
        print(f'[TeaAgent] Error getting diff: {exc}')
        return True

    return True


def _start_background_run(args: argparse.Namespace) -> int:
    from teaagent.ergonomics.background_run import (
        BackgroundRunStore,
        build_agent_run_command,
    )

    run_store = RunStore(args.root, readonly=True)
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
            print_json(
                {
                    'status': 'error',
                    'message': (
                        f"'{candidate}' looks like an existing run id. "
                        f'Use `teaagent agent resume {candidate}` or '
                        f'`teaagent agent interactive-review {candidate}` instead. '
                        '--background launches a new detached task; it is not for resuming.'
                    ),
                }
            )
            return 2
        if suspension_path.is_file():
            print_json(
                {
                    'status': 'error',
                    'message': (
                        f"'{candidate}' looks like a suspension id. "
                        f'Use `teaagent agent interactive-review {candidate}` '
                        'to inspect it; true resume is not yet available for REPL '
                        'suspensions.'
                    ),
                }
            )
            return 2

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
    # First-run orientation (shown once per workspace)
    import os as _os

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
                print_json(
                    {
                        'status': 'error',
                        'message': (
                            'Numeric --parallel requires read-only permission mode '
                            'for safe parallel analysis branches.'
                        ),
                    }
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
    adapter = args._adapter_factory(args.provider, model=selected_model)
    merged_context_extra: dict[str, Any] = dict(initial_context_extra or {})
    if resumed_from:
        merged_context_extra['resumed_from'] = resumed_from
    if plan_contract is not None:
        merged_context_extra['plan_contract'] = plan_contract.to_dict()
    gate_exit = _require_plan_gate(args, plan_contract)
    if gate_exit is not None:
        return gate_exit
    store = RunStore(args.root)
    audit = store.audit_logger()

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
            # Log but don't crash - scratchpad write is best-effort
            import logging

            logging.getLogger(__name__).warning('Scratchpad write error: %s', exc)

    import atexit

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

    from teaagent.run_undo import UndoJournal
    from teaagent.sandbox import GitBranchSandbox

    # Initialize git sandbox if available (will be updated with actual run_id later)
    git_sandbox = GitBranchSandbox(args.root, run_id='pending')
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
            if not sandbox_result.success:
                print(
                    f'[TeaAgent WARNING] Git sandbox initialization failed: {sandbox_result.error}',
                    file=sys.stderr,
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
                if not sandbox_result.success:
                    print(
                        f'[TeaAgent WARNING] Git sandbox initialization failed: {sandbox_result.error}',
                        file=sys.stderr,
                    )
                    git_sandbox_available = False
            elif choice in ('yes', 'y', ''):
                sandbox_result = git_sandbox.start(auto_stash=auto_stash)
                if not sandbox_result.success:
                    print(
                        f'[TeaAgent WARNING] Git sandbox initialization failed: {sandbox_result.error}',
                        file=sys.stderr,
                    )
                    git_sandbox_available = False
            else:
                print(
                    '[TeaAgent] Sandbox declined. Running in local workspace directly.',
                    file=sys.stderr,
                )
                git_sandbox_available = False

    undo_journal = UndoJournal(args.root)
    audit.add_sink(undo_journal)

    # Add git transaction sink if sandbox is active
    git_transaction_sink = None
    if git_sandbox_available:
        from teaagent.sandbox import GitTransactionSink

        git_transaction_sink = GitTransactionSink(git_sandbox)
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
    config = ChatAgentConfig.from_root(
        args.root,
        max_iterations=args.max_iterations,
        max_tool_calls=args.max_tool_calls,
        max_estimated_cost_cents=max_estimated_cost_cents,
        allow_destructive=args.allow_destructive,
        model=selected_model,
        permission_mode=resolved_permission_mode,
        approved_call_ids=frozenset(args.approve_call_id),
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
    result = run_chat_agent(
        config,
        task,
        adapter=adapter,
        audit=audit,
        task_spec=task_spec,
        initial_observations=initial_observations,
        initial_context_extra=merged_context_extra or None,
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

    # Handle git sandbox resolution
    if git_sandbox_available:  # noqa: SIM102 - keep sandbox resolution block indentation stable
        if git_sandbox.is_available():
            # Show diff summary
            try:
                import subprocess

                diff_result = subprocess.run(
                    ['git', 'diff', '--stat', f'{git_sandbox._original_branch}..HEAD'],
                    cwd=args.root,
                    capture_output=True,
                    text=True,
                )
                if diff_result.stdout.strip():
                    print('\n[TeaAgent] Changes in sandbox branch:')
                    print(diff_result.stdout)
                else:
                    print('\n[TeaAgent] No changes made in sandbox branch.')
            except Exception as exc:
                print('\n[TeaAgent] Could not generate diff summary.')
                logger.warning(f'Failed to generate diff summary: {exc}')

            # Prompt for resolution
            if result.status == 'completed':
                print(f"\nApply changes back to '{git_sandbox._original_branch}'?")
                # Show interactive diff before merge prompt
                if not show_interactive_diff(args.root, git_sandbox._branch_name):
                    print('[TeaAgent] Merge cancelled by user.')
                    return 0

                print(
                    '  [m]erge (normal) / [s]quash and commit / [d]iscard / [k]eep branch for review: ',
                    end='',
                )
                choice = input().strip().lower()

                if choice == 'm':
                    merge_result = git_sandbox.merge(squash=False)
                    if merge_result.success:
                        print('[TeaAgent] Merged sandbox branch successfully.')
                    elif merge_result.has_conflicts:
                        print(
                            f'[TeaAgent] Merge conflicts detected in {len(merge_result.conflicted_files)} file(s):'
                        )
                        for file in merge_result.conflicted_files:
                            print(f'  - {file}')
                        print('\nResolve conflicts:')
                        print('  [l] Let LLM auto-resolve conflicts')
                        print('  [a] Accept Agent version (theirs)')
                        print('  [d] Accept Developer version (ours)')
                        print('  [b] Abort merge and keep sandbox branch')
                        print('  [m] Launch mergetool for manual resolution')
                        resolution = input('Choice: ').strip().lower()

                        from teaagent.sandbox import (
                            abort_merge,
                            resolve_conflict_accept_ours,
                            resolve_conflict_accept_theirs,
                            resolve_conflicts_with_llm,
                        )

                        if resolution == 'l':
                            print('[TeaAgent] Using LLM to resolve conflicts...')
                            llm_results = resolve_conflicts_with_llm(
                                args.root,
                                merge_result.conflicted_files,
                                args.provider,
                                args.model,
                            )
                            resolved_count = sum(
                                1
                                for status in llm_results.values()
                                if status == 'resolved'
                            )
                            failed_count = sum(
                                1
                                for status in llm_results.values()
                                if status == 'failed'
                            )
                            skipped_count = sum(
                                1
                                for status in llm_results.values()
                                if status == 'skipped'
                            )

                            print('[TeaAgent] LLM resolution results:')
                            print(f'  Resolved: {resolved_count}')
                            print(f'  Failed: {failed_count}')
                            print(f'  Skipped: {skipped_count}')

                            if resolved_count == len(merge_result.conflicted_files):
                                # All conflicts resolved, complete the merge
                                subprocess.run(
                                    ['git', 'commit', '--no-edit'],
                                    cwd=args.root,
                                    check=True,
                                    capture_output=True,
                                )
                                subprocess.run(
                                    ['git', 'branch', '-D', git_sandbox._branch_name],
                                    cwd=args.root,
                                    check=True,
                                    capture_output=True,
                                )
                                if git_sandbox._stash_id:
                                    from teaagent.sandbox import stash_pop

                                    stash_pop(args.root)
                                print(
                                    '[TeaAgent] All conflicts resolved by LLM. Merge completed.'
                                )
                            else:
                                print(
                                    '[TeaAgent] Some conflicts could not be resolved. Manual intervention required.',
                                    file=sys.stderr,
                                )
                                abort_merge(args.root)
                                print(
                                    '[TeaAgent] Merge aborted. Sandbox branch preserved for manual resolution.',
                                    file=sys.stderr,
                                )
                        elif resolution == 'a':
                            for file in merge_result.conflicted_files:
                                if resolve_conflict_accept_theirs(args.root, file):
                                    print(f'  Accepted Agent version for {file}')
                                else:
                                    print(
                                        f'  Failed to resolve {file}', file=sys.stderr
                                    )
                            # Complete the merge
                            subprocess.run(
                                ['git', 'commit', '--no-edit'],
                                cwd=args.root,
                                check=True,
                                capture_output=True,
                            )
                            subprocess.run(
                                ['git', 'branch', '-D', git_sandbox._branch_name],
                                cwd=args.root,
                                check=True,
                                capture_output=True,
                            )
                            if git_sandbox._stash_id:
                                from teaagent.sandbox import stash_pop

                                stash_pop(args.root)
                            print('[TeaAgent] Conflicts resolved using Agent version.')
                        elif resolution == 'd':
                            for file in merge_result.conflicted_files:
                                if resolve_conflict_accept_ours(args.root, file):
                                    print(f'  Accepted Developer version for {file}')
                                else:
                                    print(
                                        f'  Failed to resolve {file}', file=sys.stderr
                                    )
                            # Complete the merge
                            subprocess.run(
                                ['git', 'commit', '--no-edit'],
                                cwd=args.root,
                                check=True,
                                capture_output=True,
                            )
                            subprocess.run(
                                ['git', 'branch', '-D', git_sandbox._branch_name],
                                cwd=args.root,
                                check=True,
                                capture_output=True,
                            )
                            if git_sandbox._stash_id:
                                from teaagent.sandbox import stash_pop

                                stash_pop(args.root)
                            print(
                                '[TeaAgent] Conflicts resolved using Developer version.'
                            )
                        elif resolution == 'b':
                            abort_merge(args.root)
                            print(
                                '[TeaAgent] Merge aborted. Sandbox branch preserved for manual resolution.'
                            )
                        elif resolution == 'm':
                            print('[TeaAgent] Launching mergetool...')
                            subprocess.run(['git', 'mergetool'], cwd=args.root)
                            # After mergetool, complete the merge
                            subprocess.run(
                                ['git', 'commit', '--no-edit'],
                                cwd=args.root,
                                check=True,
                                capture_output=True,
                            )
                            subprocess.run(
                                ['git', 'branch', '-D', git_sandbox._branch_name],
                                cwd=args.root,
                                check=True,
                                capture_output=True,
                            )
                            if git_sandbox._stash_id:
                                from teaagent.sandbox import stash_pop

                                stash_pop(args.root)
                            print(
                                '[TeaAgent] Merge completed with manual resolution.',
                                file=sys.stderr,
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
    if getattr(args, 'json_stream', False):
        from teaagent.streaming.events import StreamEvent, emit_stream_event

        emit_stream_event(StreamEvent('run_result', payload))
    else:
        print_json(payload)
    if getattr(args, 'notify', False):
        from teaagent.ergonomics.notify import notify

        notify('TeaAgent', f'Run {result.run_id} {result.status}')

    # Display recovery guidance for failed or partial success runs
    if result.status != 'completed' and not getattr(args, 'json_stream', False):
        _display_recovery_guidance(result, args, store)

    return 0 if result.status == 'completed' else 1
