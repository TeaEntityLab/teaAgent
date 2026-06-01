from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from teaagent.automations import (
    AutomationSpec,
    AutomationStore,
    AutomationTickLock,
    compute_next_run_at,
)
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.cli._output import print_json
from teaagent.code_analysis import CodeAnalysisConfig
from teaagent.daily import build_daily_brief
from teaagent.ergonomics.human_output import format_preflight_summary
from teaagent.intent import build_task_spec, clarify_task
from teaagent.model_routing import route_model
from teaagent.plan import PlanContract
from teaagent.policy import PermissionMode, parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore, summarize_audit_events
from teaagent.runner import ApprovalHandler, ApprovalRequest, RunResult
from teaagent.sandbox import ParallelExperimentStack
from teaagent.skill_candidates import SkillCandidateStore
from teaagent.subagents._review import (
    list_subagent_reviews,
    load_subagent_review,
)

logger = logging.getLogger(__name__)

# Constants for pagination and display limits
DEFAULT_DIFF_PREVIEW_LINES = 30
DEFAULT_PAGINATION_LINES = 50
DEFAULT_SESSION_GRANT_TTL_HOURS = 8.0


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

    print('\n' + formatted_advice)


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
                if not approval_store.check_scoped_approval_digest(
                    run_id=args.run_id,
                    call_id=pending['call_id'],
                    tool_name=pending['tool_name'],
                    argument_digest=digest,
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


def _resolve_validation_profile(args: argparse.Namespace) -> Optional[str]:
    if getattr(args, 'no_validate', False):
        return None
    if getattr(args, 'validate', False):
        return getattr(args, 'validation_profile', None) or 'standard'
    return None


def _require_plan_gate(
    args: argparse.Namespace, plan_contract: Optional[PlanContract]
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
    from teaagent.cli._handlers._misc import handle_first_run

    handle_first_run(Path(args.root), quiet=getattr(args, 'quiet', False))
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
    adapter = args._adapter_factory(args.provider, model=selected_model)  # type: ignore[attr-defined]
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
        except Exception:
            pass

    import atexit

    atexit.register(_write_scratchpad_on_exit)

    previous = signal.signal(signal.SIGINT, lambda sig, frame: _write_scratchpad_on_exit())
    _sp_sigint_restore: Callable[..., Any] = previous

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
        ),
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
                progress=f'Ended ({result.status})' + (
                    f': {error_msg[:200]}' if error_msg else ''),
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
    if git_sandbox_available:
        # Re-create sandbox with actual run_id for proper branch naming
        git_sandbox = GitBranchSandbox(args.root, run_id=result.run_id)
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
                                    '[TeaAgent] Some conflicts could not be resolved. Manual intervention required.'
                                )
                                abort_merge(args.root)
                                print(
                                    '[TeaAgent] Merge aborted. Sandbox branch preserved for manual resolution.'
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
    payload = run_result_payload(
        result,
        routing=routing.to_dict() if routing else None,
        audit_summary=summarize_audit_events(events),
        permission_mode=resolved_permission_mode.value,
    )
    if not getattr(args, 'no_summary', False):
        from teaagent.budget import RunBudget
        from teaagent.ergonomics.run_summary import summarize_run

        cap = (
            int(args.max_estimated_cost_cents)
            if int(getattr(args, 'max_estimated_cost_cents', 0) or 0) > 0
            else RunBudget().max_estimated_cost_cents
        )
        payload['run_summary'] = summarize_run(
            root=args.root,
            run_id=result.run_id,
            events=events,
            cost_cents=result.cost_cents,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            budget_cap_cents=cap,
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

    # Display recovery guidance for failed or partial success runs
    if result.status != 'completed' and not getattr(args, 'json_stream', False):
        _display_recovery_guidance(result, args, store)

    return 0 if result.status == 'completed' else 1


def show_interactive_diff(root: str | Path, sandbox_branch: str) -> bool:
    """Show interactive diff before merge prompt.

    Args:
        root: The workspace root directory
        sandbox_branch: The sandbox branch name

    Returns:
        True if user wants to proceed, False to cancel
    """
    import subprocess
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


def _load_suspension_data(root_path: Path, run_id: str) -> dict[str, Any] | None:
    """Load and validate suspension data for a given run_id.

    Args:
        root_path: The workspace root directory
        run_id: The background task run_id to review

    Returns:
        Suspension data dict, or None if loading fails
    """
    tea_dir = root_path / '.teaagent'
    suspension_file = tea_dir / f'suspension-{run_id}.json'

    if not suspension_file.exists():
        print(f'[TeaAgent] Error: No suspension data found for run_id {run_id}')
        print(f'[TeaAgent] Expected file: {suspension_file}')
        return None

    try:
        with open(suspension_file) as f:
            suspension_data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f'[TeaAgent] Error: Corrupted suspension data: {exc}')
        return None
    except Exception as exc:
        print(f'[TeaAgent] Error loading suspension data: {exc}')
        return None

    # Verify ACP compliance
    if 'acp_version' not in suspension_data:
        print('[TeaAgent] Warning: Suspension data missing ACP version field')

    return suspension_data


def _display_review_header(run_id: str, suspension_data: dict[str, Any]) -> None:
    """Display the review mode header with run information.

    Args:
        run_id: The background task run_id
        suspension_data: The loaded suspension data
    """
    print('\n=== Interactive Review Mode ===')
    print(f'Reviewing results from run: {run_id}')
    print(f'Original mode: {suspension_data.get("mode", "unknown")}')
    print(
        f'Suspended at: {__import__("time").ctime(suspension_data.get("timestamp", 0))}'
    )
    print()


def _get_changed_files(root_path: Path) -> list[str] | None:
    """Get list of changed files from git.

    Args:
        root_path: The workspace root directory

    Returns:
        List of changed file paths, or None if git fails
    """
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            print('[TeaAgent] No changes detected to review.')
            return None

        return result.stdout.strip().split('\n')
    except FileNotFoundError:
        print('[TeaAgent] Git not found in PATH')
        return None
    except Exception as exc:
        print(f'[TeaAgent] Error getting changed files: {exc}')
        return None


def _display_file_list(changed_files: list[str]) -> None:
    """Display the list of changed files and review commands.

    Args:
        changed_files: List of changed file paths
    """
    print(f'Found {len(changed_files)} changed file(s) to review:')
    for i, file in enumerate(changed_files, 1):
        print(f'  {i}. {file}')

    print()
    print('Review commands:')
    print('  y - Accept file changes')
    print('  e - Edit file in external editor')
    print('  r - Reject and request AI reconsideration')
    print('  n - Next file (skip)')
    print('  q - Quit review')
    print()


def _show_file_diff(root_path: Path, file_path: str) -> None:
    """Display git diff for a specific file.

    Args:
        root_path: The workspace root directory
        file_path: Path to the file to show diff for
    """
    diff_result = subprocess.run(
        ['git', 'diff', '--color=always', file_path],
        cwd=root_path,
        capture_output=True,
        text=True,
    )

    if diff_result.stdout:
        # Show limited diff (first 20 lines)
        diff_lines = diff_result.stdout.split('\n')
        print('\n'.join(diff_lines[:20]))
        if len(diff_lines) > 20:
            print(f'... ({len(diff_lines) - 20} more lines)')


def _handle_review_choice(
    choice: str,
    file_path: str,
    root_path: Path,
    review_decisions: dict[str, str],
) -> bool:
    """Handle user's review choice for a file.

    Args:
        choice: User's choice (y/e/r/n/q)
        file_path: Path to the file being reviewed
        root_path: The workspace root directory
        review_decisions: Dict to store review decisions

    Returns:
        True if review should continue, False if user quit
    """
    if choice == 'y':
        review_decisions[file_path] = 'accepted'
        print(f'✓ Accepted {file_path}')
        return True
    elif choice == 'e':
        # Open in external editor
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.run([editor, str(root_path / file_path)], cwd=root_path)
        review_decisions[file_path] = 'edited'
        print(f'✓ Edited {file_path}')
        return True
    elif choice == 'r':
        review_decisions[file_path] = 'rejected'
        print(f'✗ Rejected {file_path} (marked for AI reconsideration)')
        # Apply rejection by reverting the file
        subprocess.run(
            ['git', 'checkout', '--', file_path],
            cwd=root_path,
            capture_output=True,
        )
        print(f'  Reverted changes to {file_path}')
        return True
    elif choice == 'n':
        print(f'→ Skipped {file_path}')
        return True
    elif choice == 'q':
        print('Review quit by user.')
        return False
    else:
        print('Invalid choice. Please try again.')
        return True


def _display_review_summary(
    review_decisions: dict[str, str], changed_files: list[str]
) -> None:
    """Display summary of review decisions.

    Args:
        review_decisions: Dict of file path to decision
        changed_files: List of all changed files
    """
    print('\n=== Review Summary ===')
    accepted = sum(1 for d in review_decisions.values() if d == 'accepted')
    edited = sum(1 for d in review_decisions.values() if d == 'edited')
    rejected = sum(1 for d in review_decisions.values() if d == 'rejected')

    print(f'Accepted: {accepted}')
    print(f'Edited: {edited}')
    print(f'Rejected: {rejected}')
    print(f'Skipped: {len(changed_files) - len(review_decisions)}')


def _save_review_decisions(
    tea_dir: Path,
    run_id: str,
    review_decisions: dict[str, str],
    suspension_data: dict[str, Any],
    changed_files: list[str],
) -> None:
    """Save review decisions to file with ACP compliance.

    Args:
        tea_dir: The .teaagent directory
        run_id: The background task run_id
        review_decisions: Dict of file path to decision
        suspension_data: The loaded suspension data
        changed_files: List of all changed files
    """
    review_file = tea_dir / f'review-{run_id}.json'

    try:
        with open(review_file, 'w') as f:
            json.dump(
                {
                    'run_id': run_id,
                    'timestamp': time.time(),
                    'acp_version': '1.0.0',  # ACP protocol version
                    'mode': 'interactive_review',  # Track current mode
                    'decisions': review_decisions,
                    'audit_trail': {
                        'review_time': time.time(),
                        'original_mode': suspension_data.get('mode', 'unknown'),
                        'transition_type': 'robot_to_keyboard',
                        'files_reviewed': len(changed_files),
                        'suspension_data': suspension_data.get('audit_trail', {}),
                    },
                },
                f,
                indent=2,
            )
        print(f'\nReview decisions saved to {review_file}')
    except Exception as exc:
        print(f'Warning: Could not save review decisions: {exc}')


def interactive_review_mode(root: str | Path, run_id: str) -> int:
    """Launch interactive review mode for background task results.

    Args:
        root: The workspace root directory
        run_id: The background task run_id to review

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    from pathlib import Path

    root_path = Path(root).resolve()

    # Load and validate suspension data
    suspension_data = _load_suspension_data(root_path, run_id)
    if suspension_data is None:
        return 1

    # Display review header
    _display_review_header(run_id, suspension_data)

    # Get changed files from git
    changed_files = _get_changed_files(root_path)
    if changed_files is None:
        return 1

    # Display file list and commands
    _display_file_list(changed_files)

    # Interactive review loop
    current_index = 0
    review_decisions: dict[str, str] = {}

    while current_index < len(changed_files):
        file_path = changed_files[current_index]
        print(
            f'\n--- Reviewing file {current_index + 1}/{len(changed_files)}: {file_path} ---'
        )

        # Show diff for this file
        _show_file_diff(root_path, file_path)

        print(f'\nAction for {file_path} [y/e/r/n/q]: ', end='')
        choice = input().strip().lower()

        should_continue = _handle_review_choice(
            choice, file_path, root_path, review_decisions
        )
        if not should_continue:
            return 0  # Early exit on quit
        elif choice in ('y', 'e', 'r', 'n'):
            current_index += 1

    # Display summary
    _display_review_summary(review_decisions, changed_files)

    # Save review decisions
    tea_dir = root_path / '.teaagent'
    _save_review_decisions(
        tea_dir, run_id, review_decisions, suspension_data, changed_files
    )

    return 0


def interactive_review_command(args: argparse.Namespace) -> int:
    """CLI command for interactive review mode."""
    return interactive_review_mode(args.root, args.run_id)


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
                path = (
                    request.arguments.get('path')
                    or request.arguments.get('TargetFile')
                    or request.arguments.get('target_file')
                    or request.arguments.get('AbsolutePath')
                )
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
                store.grant(
                    request.tool_name,
                    scope='session',
                    permission_mode=permission_mode,
                    ttl_hours=DEFAULT_SESSION_GRANT_TTL_HOURS,
                )
                print(
                    f'[TeaAgent] No path found in tool arguments. Registered global session grant for {request.tool_name}',
                    file=sys.stderr,
                )
            return True
        elif answer == 't':
            store.grant(
                request.tool_name,
                scope='session',
                permission_mode=permission_mode,
                ttl_hours=8.0,
            )
            print(
                f'[TeaAgent] Registered global session grant for {request.tool_name}',
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
    if args.human:
        print(format_preflight_summary(report.to_dict(), root=args.root))
    else:
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

    preview = getattr(args, 'preview', False)

    # Try git sandbox rollback first
    git_sandbox = GitBranchSandbox(args.root, run_id=run_id)
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
    store = RunStore(args.root, readonly=True)
    try:
        print_json(store.heartbeat_for_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def agent_runs_list(args: argparse.Namespace) -> int:
    store = RunStore(args.root, readonly=True)
    payload = [summary.to_dict() for summary in store.list_runs(limit=args.limit)]
    from teaagent.scratchpad import Scratchpad

    scratchpad = Scratchpad(Path(args.root))
    if scratchpad.exists():
        content = scratchpad.read()
        if content and content.get('last_goal'):
            payload.append({'scratchpad_last_goal': content['last_goal']})
    print_json(payload)
    return 0


def agent_runs_trace(args: argparse.Namespace) -> int:
    from teaagent.run_trace import build_run_trace, format_trace_text

    store = RunStore(args.root, readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    trace = build_run_trace(events)
    if getattr(args, 'text', False):
        print(format_trace_text(trace))
        return 0
    print_json({'run_id': args.run_id, 'trace': trace})
    return 0


def agent_runs_export(args: argparse.Namespace) -> int:
    from teaagent.run_trace import dumps_export, export_run

    store = RunStore(args.root, readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print(dumps_export(export_run(events, run_id=args.run_id)))
    return 0


def agent_runs_replay(args: argparse.Namespace) -> int:
    from teaagent.run_trace import dumps_export, replay_dry_run

    store = RunStore(args.root, readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print(dumps_export(replay_dry_run(events, run_id=args.run_id)))
    return 0


def agent_run_show(args: argparse.Namespace) -> int:
    store = RunStore(args.root, readonly=True)
    try:
        print_json(store.show_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
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


def _execute_parallel_experiment(
    args: argparse.Namespace, task: str, parallel_options: str
) -> int:
    """Execute parallel experiments using ParallelExperimentStack.

    Args:
        args: CLI arguments.
        task: Task description.
        parallel_options: Comma-separated options (e.g., opt1,opt2,opt3).

    Returns:
        Exit code.
    """
    from uuid import uuid4

    options = [opt.strip() for opt in parallel_options.split(',') if opt.strip()]
    if not options:
        print_json(
            {
                'status': 'error',
                'message': 'No options provided for parallel experiment',
            }
        )
        return 1

    run_id = uuid4().hex
    root = Path(args.root).resolve()

    # Create parallel experiment stack
    stack = ParallelExperimentStack(root, run_id, options)

    # Start all sandboxes
    print_json(
        {
            'status': 'starting_parallel_experiments',
            'run_id': run_id,
            'options': options,
            'message': f'Starting {len(options)} parallel experiment branches',
        }
    )

    start_results = stack.start_all(
        auto_stash=getattr(args, 'git_sandbox_auto_stash', False)
    )

    failed = [opt for opt, success in start_results.items() if not success]
    if failed:
        print_json(
            {
                'status': 'error',
                'message': f'Failed to start {len(failed)} sandbox branches',
                'failed_options': failed,
            }
        )
        return 1

    branches: dict[str, str | None] = {}
    for opt in options:
        sandbox = stack.get_sandbox(opt)
        if sandbox is not None:
            # Access branch_name as a public attribute
            branch_name = getattr(sandbox, '_branch_name', None)
            branches[opt] = str(branch_name) if branch_name is not None else None
        else:
            branches[opt] = None

    print_json(
        {
            'status': 'parallel_experiments_started',
            'run_id': run_id,
            'options': options,
            'branches': branches,
            'message': 'Use "teaagent experiment compare" to compare results, then "teaagent experiment select" to merge the best option',
        }
    )

    return 0
