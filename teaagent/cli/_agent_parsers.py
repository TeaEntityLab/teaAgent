from __future__ import annotations

import argparse
from typing import Any, Callable, Optional, cast

from teaagent.policy import PermissionMode


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable[..., Any]],
) -> None:
    agent = subparsers.add_parser('agent', help='Run model-driven agent tasks.')
    subs = agent.add_subparsers(dest='agent_command', required=True)
    _run(subs, handlers['run'])
    _preflight(subs, handlers['preflight'])
    _plan(subs, handlers['plan'])
    _daily(subs, handlers['daily'])
    _resume(subs, handlers['resume'])
    _undo(subs, handlers['undo'])
    _status(subs, handlers['status'])
    _runs(subs, cast(dict[str, Callable[..., Any]], handlers['runs']))
    _show(subs, handlers['show'])
    _card(subs, handlers['card'])
    if 'attach' in handlers:
        _attach(subs, handlers['attach'])
    if 'subagent_review_list' in handlers:
        _subagent_review(
            subs,
            {
                'list': handlers['subagent_review_list'],
                'show': handlers['subagent_review_show'],
                'check': handlers['subagent_review_check'],
                'apply': handlers['subagent_review_apply'],
            },
        )
    if 'chat' in handlers:
        _chat(subs, handlers['chat'])
    if 'interactive_review' in handlers:
        _interactive_review(subs, handlers['interactive_review'])
    if 'automation_add' in handlers:
        _automation(
            subs,
            {
                'add': handlers['automation_add'],
                'list': handlers['automation_list'],
                'show': handlers['automation_show'],
                'pause': handlers['automation_pause'],
                'resume': handlers['automation_resume'],
                'delete': handlers['automation_delete'],
                'run': handlers['automation_run'],
                'tick': handlers['automation_tick'],
                'serve': handlers['automation_serve'],
                'status': handlers['automation_status'],
                'template': handlers['automation_template'],
                'promote': handlers['automation_promote'],
            },
        )


def add_agent_run_arguments(
    p: argparse.ArgumentParser, *, include_task_positional: bool = False
) -> None:
    if include_task_positional:
        # Chat mode: task comes first, provider is optional after
        p.add_argument(
            'task',
            nargs='?',
            default=None,
            help='Task for the agent to perform (optional when --from-plan is set).',
        )
        p.add_argument(
            'provider',
            nargs='?',
            default=None,
            metavar='provider',
            help='Model provider (optional when set in .teaagent/config.toml).',
        )
    else:
        # Standard run mode: provider comes first, task is optional after
        p.add_argument(
            'provider',
            nargs='?',
            default=None,
            metavar='provider',
            help='Model provider (optional when set in .teaagent/config.toml).',
        )
        p.add_argument(
            'task',
            nargs='?',
            default=None,
            help='Task for the agent to perform (optional when --from-plan is set).',
        )
    p.add_argument(
        '--from-plan',
        default=None,
        metavar='PATH',
        help='Load task and provenance from a .teaagent/plans/*.md artifact.',
    )
    p.add_argument(
        '--allow-external-plan',
        action='store_true',
        help=('Allow plan paths elsewhere under --root (not only .teaagent/plans/).'),
    )
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model',
        action='store_true',
        help=(
            'Choose a provider-specific model from the task category '
            'when --model is not set.'
        ),
    )
    p.add_argument(
        '--max-iterations', type=int, default=10, help='Maximum agent loop iterations.'
    )
    p.add_argument('--max-tool-calls', type=int, default=10, help='Maximum tool calls.')
    p.add_argument(
        '--max-estimated-cost-cents',
        type=int,
        default=0,
        help=(
            'Abort the run when estimated cost exceeds this cap '
            '(0 uses default budget).'
        ),
    )
    p.add_argument(
        '--clarify',
        action='store_true',
        help='Run deterministic ambiguity scoring before calling the model.',
    )
    p.add_argument(
        '--allow-destructive',
        action='store_true',
        help='Allow destructive tools such as write, patch, and shell.',
    )
    p.add_argument(
        '--git-sandbox',
        action='store_true',
        help='Run agent task in a git sandbox branch for safe rollbacks.',
    )
    p.add_argument(
        '--git-sandbox-auto-stash',
        action='store_true',
        help='Automatically stash dirty worktree before creating git sandbox branch.',
    )
    p.add_argument(
        '--parallel',
        default=None,
        metavar='N',
        type=int,
        help=(
            'Run tournament mode with N parallel approaches. '
            'Creates isolated sandbox branches for each approach.'
        ),
    )
    p.add_argument(
        '--approach',
        action='append',
        default=[],
        help='Custom approach hint for tournament mode. Can be repeated.',
    )
    p.add_argument(
        '--no-benchmark',
        action='store_true',
        help='Skip performance benchmarking in tournament mode.',
    )
    p.add_argument(
        '--approve-call-id',
        action='append',
        default=[],
        help='Approve one exact destructive tool call id. Can be repeated.',
    )
    p.add_argument(
        '--hitl-approval',
        action='store_true',
        help=(
            'Prompt before executing unapproved destructive tool calls '
            'in prompt permission mode.'
        ),
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for workspace tools.',
    )
    p.add_argument(
        '--subagent',
        action='store_true',
        help="Expose the 'subagent' tool so the model can delegate sub-tasks.",
    )
    p.add_argument(
        '--max-subagent-depth',
        type=int,
        default=1,
        help='Maximum nested subagent depth.',
    )
    p.add_argument(
        '--heartbeat',
        type=float,
        default=0.0,
        help=(
            'Emit a heartbeat audit event every N seconds while running. 0 disables.'
        ),
    )
    p.add_argument(
        '--code-analysis',
        action='store_true',
        help=(
            'Enable LSP-backed code analysis tools '
            '(code_definition/code_references/code_diagnostics).'
        ),
    )
    p.add_argument(
        '--validate',
        action='store_true',
        help='Run post-run validation (default profile: standard).',
    )
    p.add_argument(
        '--validation-profile',
        choices=['fast', 'standard', 'strict'],
        default=None,
        help='Validation profile when --validate is set (default: standard).',
    )
    p.add_argument(
        '--no-validate',
        action='store_true',
        help='Disable validation even if configured.',
    )
    p.add_argument(
        '--require-plan',
        action='store_true',
        help='Block workspace writes unless --from-plan bound a plan artifact.',
    )
    p.add_argument(
        '--skip-plan-check',
        action='store_true',
        help=(
            'Skip plan-before-write enforcement (not recommended). '
            'Use only when you understand the security implications.'
        ),
    )
    p.add_argument(
        '--telemetry-otlp-endpoint',
        default=None,
        metavar='URL',
        help=(
            'Export OpenTelemetry traces to this OTLP HTTP endpoint '
            '(e.g. http://localhost:4318/v1/traces).'
        ),
    )
    p.add_argument(
        '--telemetry-service-name',
        default='teaagent',
        help='OTel service.name resource attribute. Default: teaagent.',
    )
    p.add_argument(
        '--telemetry-console',
        action='store_true',
        help='Also print OpenTelemetry spans to stderr (debug).',
    )
    p.add_argument(
        '--checkpoint-store',
        default=None,
        metavar='PATH',
        help=(
            'SQLite path for run checkpoint storage. '
            'Saves context after each tool call.'
        ),
    )
    p.add_argument(
        '--dry-run',
        action='store_true',
        help='Plan the run (preflight + token budget) without calling the model.',
    )
    p.add_argument(
        '--human',
        action='store_true',
        help=('With --dry-run, print a beginner-friendly summary instead of JSON.'),
    )
    p.add_argument(
        '--background',
        action='store_true',
        help=('Run detached; use agent attach <run_id> --follow to stream events.'),
    )
    p.add_argument(
        '--progress',
        action='store_true',
        default=None,
        help=(
            'Stream brief progress lines to stderr during the run '
            '(default: on when stderr is a TTY).'
        ),
    )
    p.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable progress lines even on a TTY.',
    )
    p.add_argument(
        '--no-summary',
        action='store_true',
        help='Suppress the post-run summary payload fields.',
    )
    p.add_argument(
        '--stream',
        action='store_true',
        help=(
            'Stream user-visible model text during the run (final-answer content only).'
        ),
    )
    p.add_argument(
        '--stream-raw',
        action='store_true',
        help='With --stream, emit raw model tokens (includes structured decision JSON).',
    )
    p.add_argument(
        '--json-stream',
        action='store_true',
        help='Emit NDJSON stream events (progress and text deltas) on stdout.',
    )
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Context budget profile for memory and replay limits.',
    )
    p.add_argument(
        '--memory-limit',
        type=int,
        default=None,
        help='Maximum number of memory entries to include in context.',
    )
    p.add_argument(
        '--skill',
        action='append',
        default=[],
        metavar='NAME',
        help='Load only this skill by name (repeatable).',
    )
    p.add_argument(
        '--no-auto-skills',
        action='store_true',
        help='Do not eager-load discovered skills into the system prompt.',
    )
    p.add_argument(
        '--skill-index-only',
        action='store_true',
        help='Inject skill metadata index only (no SKILL.md bodies in the prompt).',
    )


def register_top_level_agent_aliases(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable[..., Any]],
) -> None:
    """Register daily-workflow aliases visible in ``teaagent --help``."""
    _run(
        subparsers,
        handlers['run'],
        help='Run one autonomous task (alias for agent run).',
        defaults={'command': 'agent', 'agent_command': 'run'},
    )
    ask = subparsers.add_parser(
        'ask',
        help='Run one agent task (alias for agent run).',
        description='Run one autonomous task with workspace tools.',
    )
    add_agent_run_arguments(ask)
    ask.set_defaults(func=handlers['run'], command='agent', agent_command='run')

    _daily(subparsers, handlers['daily'], top_level=True)
    _preflight(subparsers, handlers['preflight'], top_level=True)
    _plan(subparsers, handlers['plan'], top_level=True)
    _resume(subparsers, handlers['resume'], top_level=True)
    _runs(
        subparsers,
        cast(dict[str, Callable[..., Any]], handlers['runs']),
        top_level=True,
    )
    if 'chat' in handlers:
        _chat(
            subparsers,
            handlers['chat'],
            help='Interactive chat REPL (alias for agent chat).',
            defaults={'command': 'agent', 'agent_command': 'chat'},
        )


def _run(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    *,
    help: str = 'Run one autonomous task with workspace tools.',
    defaults: Optional[dict[str, object]] = None,
) -> None:
    p = subs.add_parser(
        'run',
        help=help,
        description='Run one autonomous task with workspace tools.',
    )
    add_agent_run_arguments(p)
    base_defaults = {'func': handler, 'agent_command': 'run'}
    if defaults:
        base_defaults.update(defaults)
    p.set_defaults(**base_defaults)


def _preflight(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    *,
    top_level: bool = False,
) -> None:
    help_text = (
        'Summarize clarify, routing, memory, and tool state without calling a model.'
    )
    p = subs.add_parser(
        'preflight' if not top_level else 'preflight',
        help=help_text,
    )
    p.add_argument(
        'provider',
        nargs='?',
        default=None,
        metavar='provider',
        help='Model provider (optional when set in .teaagent/config.toml).',
    )
    p.add_argument('task', help='Task to evaluate.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model', action='store_true', help='Apply task category routing.'
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode to report.',
    )
    p.add_argument(
        '--memory-limit',
        type=int,
        default=5,
        help='Maximum matched memories to include.',
    )
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Read-only context budget profile for preflight evidence.',
    )
    p.add_argument(
        '--human',
        action='store_true',
        help='Print a beginner-friendly readiness summary instead of JSON.',
    )
    defaults: dict[str, object] = {'func': handler, 'agent_command': 'preflight'}
    if top_level:
        defaults['command'] = 'agent'
    p.set_defaults(**defaults)


def _plan(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    *,
    top_level: bool = False,
) -> None:
    p = subs.add_parser(
        'plan',
        help='Create a reviewable read-only plan artifact without calling a model.',
    )
    p.add_argument(
        'provider',
        nargs='?',
        default=None,
        metavar='provider',
        help='Model provider (optional when set in .teaagent/config.toml).',
    )
    p.add_argument('task', help='Task to plan.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model', action='store_true', help='Apply task category routing.'
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.READ_ONLY.value,
        help='Permission mode to report (default: read-only planning).',
    )
    p.add_argument(
        '--memory-limit',
        type=int,
        default=5,
        help='Maximum matched memories to include.',
    )
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Read-only context budget profile for planning evidence.',
    )
    p.add_argument(
        '--human',
        action='store_true',
        help='Print a beginner-friendly planning summary instead of JSON.',
    )
    p.add_argument(
        '--no-write',
        action='store_true',
        help='Skip writing .teaagent/plans/*.md artifact.',
    )
    defaults: dict[str, object] = {'func': handler, 'agent_command': 'plan'}
    if top_level:
        defaults['command'] = 'agent'
    p.set_defaults(**defaults)


def _daily(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    *,
    top_level: bool = False,
) -> None:
    p = subs.add_parser(
        'daily',
        help='Show read-only daily readiness, run, health, and token budget summary.',
    )
    p.add_argument(
        'provider',
        nargs='?',
        default=None,
        metavar='provider',
        help='Model provider (optional when set in .teaagent/config.toml).',
    )
    p.add_argument('task', nargs='?', default=None, help='Optional task to evaluate.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model', action='store_true', help='Apply task category routing.'
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode to report and recommend.',
    )
    p.add_argument(
        '--memory-limit',
        type=int,
        default=None,
        help='Override matched memories included by the selected context profile.',
    )
    p.add_argument(
        '--runs-limit', type=int, default=5, help='Maximum recent runs to summarize.'
    )
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Read-only context budget profile.',
    )
    p.add_argument(
        '--dry-run',
        action='store_true',
        help='Emit preflight and token budget without persisting a journal run.',
    )
    p.add_argument(
        '--human',
        action='store_true',
        help='Print a beginner-friendly readiness summary instead of JSON.',
    )
    p.add_argument(
        '--write-journal',
        action='store_true',
        help='Write .teaagent/daily/YYYY-MM-DD.md from the daily brief.',
    )
    defaults: dict[str, object] = {'func': handler, 'agent_command': 'daily'}
    if top_level:
        defaults['command'] = 'agent'
    p.set_defaults(**defaults)


def _attach(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'attach', help='Attach to a run (heartbeat snapshot or live event stream).'
    )
    p.add_argument('run_id', help='Run id to attach.')
    p.add_argument('--root', default='.', help='Workspace root.')
    p.add_argument(
        '--follow',
        action='store_true',
        help='Stream new audit events until the run completes.',
    )
    p.add_argument(
        '--json-stream',
        action='store_true',
        help='Emit normalized NDJSON stream events instead of raw audit rows.',
    )
    p.add_argument(
        '--resume',
        action='store_true',
        help='Resume a paused run after snapshot (auto-approve pending destructive call).',
    )
    p.add_argument(
        '--notify',
        action='store_true',
        help='Emit a desktop notification with the current run status.',
    )
    p.set_defaults(func=handler, agent_command='attach')


def _chat(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    *,
    help: str = 'Interactive chat REPL for continuous agent interaction.',
    defaults: Optional[dict[str, object]] = None,
) -> None:
    p = subs.add_parser('chat', help=help)
    # Use shared run arguments with task as first positional (chat-specific order)
    add_agent_run_arguments(p, include_task_positional=True)
    base_defaults = {'func': handler, 'agent_command': 'chat'}
    if defaults:
        base_defaults.update(defaults)
    p.set_defaults(**base_defaults)


def _interactive_review(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'interactive-review',
        help='Interactive review mode for background task results.',
    )
    p.add_argument('run_id', help='Background task run ID to review.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.set_defaults(func=handler, agent_command='interactive_review')


def _resume(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
    *,
    top_level: bool = False,
) -> None:
    p = subs.add_parser(
        'resume',
        help="Re-run a persisted run's task using the original recorded task.",
    )
    p.add_argument(
        'provider',
        nargs='?',
        default=None,
        metavar='provider',
        help='Model provider (optional when set in .teaagent/config.toml).',
    )
    p.add_argument('run_id', help='Run id to resume.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model', action='store_true', help='Apply task category routing.'
    )
    p.add_argument(
        '--max-iterations', type=int, default=10, help='Maximum agent loop iterations.'
    )
    p.add_argument('--max-tool-calls', type=int, default=10, help='Maximum tool calls.')
    p.add_argument(
        '--clarify',
        action='store_true',
        help='Run deterministic ambiguity scoring before calling the model.',
    )
    p.add_argument(
        '--allow-destructive', action='store_true', help='Allow destructive tools.'
    )
    p.add_argument(
        '--approve-call-id',
        action='append',
        default=[],
        help='Approve one exact destructive tool call id. Can be repeated.',
    )
    p.add_argument(
        '--hitl-approval',
        action='store_true',
        help='Prompt before unapproved destructive tool calls.',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for workspace tools.',
    )
    p.add_argument(
        '--subagent', action='store_true', help="Expose the 'subagent' tool."
    )
    p.add_argument(
        '--max-subagent-depth',
        type=int,
        default=1,
        help='Maximum nested subagent depth.',
    )
    p.add_argument(
        '--heartbeat',
        type=float,
        default=0.0,
        help='Heartbeat interval seconds. 0 disables.',
    )
    p.add_argument(
        '--code-analysis',
        action='store_true',
        help=(
            'Enable LSP-backed code analysis tools '
            '(code_definition/code_references/code_diagnostics).'
        ),
    )
    p.add_argument(
        '--fresh-restart',
        action='store_true',
        help='Re-run the original task from scratch instead of replaying observations from the prior run.',
    )
    p.add_argument(
        '--checkpoint-store',
        default=None,
        metavar='PATH',
        help='SQLite path for checkpoint storage. Used to restore compacted context on resume.',
    )
    p.add_argument(
        '--auto-compact',
        action=argparse.BooleanOptionalAction,
        default=None,
        help='Truncate replayed observations when resuming long runs (default from config).',
    )
    p.add_argument(
        '--progress',
        action='store_true',
        default=None,
        help='Stream progress to stderr.',
    )
    p.add_argument('--no-progress', action='store_true', help='Disable progress lines.')
    p.add_argument(
        '--stream', action='store_true', help='Stream user-visible model text.'
    )
    p.add_argument('--stream-raw', action='store_true', help='Stream raw model tokens.')
    p.add_argument(
        '--json-stream',
        action='store_true',
        help='Emit NDJSON stream events on stdout.',
    )
    defaults: dict[str, object] = {'func': handler, 'agent_command': 'resume'}
    if top_level:
        defaults['command'] = 'agent'
    p.set_defaults(**defaults)


def _undo(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'undo',
        help='Restore workspace files captured before an agent run.',
    )
    p.add_argument(
        'run_id',
        nargs='?',
        default=None,
        help='Run id to undo. Defaults to the most recent run with an undo journal.',
    )
    p.add_argument(
        '--last',
        action='store_true',
        help='Undo the most recent run with an undo journal (default when run_id is omitted).',
    )
    p.add_argument(
        '--preview',
        action='store_true',
        help='Show a unified diff of what would be restored, without applying changes.',
    )
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.set_defaults(func=handler, agent_command='undo')


def _status(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser('status', help='Show liveness status of a persisted run.')
    p.add_argument('run_id', help='Run id to inspect.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.set_defaults(func=handler)


def _automation(
    subs: argparse._SubParsersAction, handlers: dict[str, Callable]
) -> None:  # type: ignore[type-arg]
    automation = subs.add_parser('automation', help='Manage persistent automations.')
    commands = automation.add_subparsers(dest='automation_command', required=True)

    add = commands.add_parser('add', help='Create a scheduled automation.')
    add.add_argument('name', help='Human readable automation name.')
    add.add_argument('task', help='Task prompt to run on schedule.')
    add.add_argument(
        '--schedule',
        required=True,
        help="Schedule expression: 'every 30m', 'every 2h', or 'daily HH:MM'.",
    )
    add.add_argument('--root', default='.', help='Workspace root.')
    add.add_argument('--provider', default=None, help='Provider override.')
    add.add_argument('--model', default=None, help='Model override.')
    add.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.READ_ONLY.value,
        help='Permission mode used for automation runs.',
    )
    add.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Context profile for automation runs.',
    )
    add.add_argument('--max-iterations', type=int, default=10)
    add.add_argument('--max-tool-calls', type=int, default=10)
    add.add_argument(
        '--auto-propose-skill',
        action='store_true',
        help='After a completed run, auto-propose a skill candidate from the run summary.',
    )
    add.add_argument(
        '--acceptance-criteria',
        default='',
        help='Observable pass/fail checks for the scheduled task (required for --dry-run).',
    )
    add.add_argument(
        '--skill',
        action='append',
        default=[],
        metavar='NAME',
        help='Explicit skill names to load for each automation run (default: none).',
    )
    add.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate the automation ticket without creating or invoking a model.',
    )
    add.add_argument(
        '--human',
        action='store_true',
        help='With --dry-run, include a readable checklist in the JSON payload.',
    )
    add.add_argument(
        '--collector-command',
        default='',
        help='Shell command run before the agent; stdout JSON may set wake_agent=false.',
    )
    add.add_argument(
        '--no-agent',
        action='store_true',
        help='Run collector_command only; never invoke the LLM (requires --collector-command).',
    )
    add.add_argument(
        '--write-source',
        choices=['local', 'agent_run', 'web_message'],
        default='local',
        help='Provenance source for this automation write (web_message quarantines unless attested).',
    )
    add.add_argument(
        '--i-attest-untrusted-write',
        action='store_true',
        help='One-shot owner attestation after reviewing an untrusted web/message payload.',
    )
    add.set_defaults(func=handlers['add'], agent_command='automation')
    _add_automation_v2_arguments(add)

    template = commands.add_parser(
        'template',
        help='Dry-run a built-in automation template (repo-watch, ...).',
    )
    template.add_argument(
        'template_name',
        help='Template name (for example repo-watch).',
    )
    template.add_argument('--root', default='.', help='Workspace root.')
    template.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Validate the template ticket without creating or invoking a model.',
    )
    template.add_argument(
        '--human',
        action='store_true',
        help='Include a readable checklist in the JSON payload.',
    )
    template.set_defaults(func=handlers['template'], agent_command='automation')

    status = commands.add_parser(
        'status', help='Show automation health and last output.'
    )
    status.add_argument('automation_id', nargs='?', default=None)
    status.add_argument('--root', default='.', help='Workspace root.')
    status.set_defaults(func=handlers['status'], agent_command='automation')

    lst = commands.add_parser('list', help='List automations.')
    lst.add_argument('--root', default='.', help='Workspace root.')
    lst.add_argument(
        '--quarantined',
        action='store_true',
        help='List quarantined automations awaiting promote.',
    )
    lst.set_defaults(func=handlers['list'], agent_command='automation')

    promote = commands.add_parser(
        'promote', help='Promote a quarantined automation to the active schedule.'
    )
    promote.add_argument('automation_id')
    promote.add_argument('--root', default='.', help='Workspace root.')
    promote.add_argument(
        '--i-attest-untrusted-write',
        action='store_true',
        help='Required when the quarantined automation came from an untrusted web/message source.',
    )
    promote.set_defaults(func=handlers['promote'], agent_command='automation')

    show = commands.add_parser('show', help='Show one automation.')
    show.add_argument('automation_id')
    show.add_argument('--root', default='.', help='Workspace root.')
    show.set_defaults(func=handlers['show'], agent_command='automation')

    pause = commands.add_parser('pause', help='Pause an automation.')
    pause.add_argument('automation_id')
    pause.add_argument('--root', default='.', help='Workspace root.')
    pause.set_defaults(func=handlers['pause'], agent_command='automation')

    resume = commands.add_parser('resume', help='Resume an automation.')
    resume.add_argument('automation_id')
    resume.add_argument('--root', default='.', help='Workspace root.')
    resume.set_defaults(func=handlers['resume'], agent_command='automation')

    delete = commands.add_parser('delete', help='Delete an automation.')
    delete.add_argument('automation_id')
    delete.add_argument('--root', default='.', help='Workspace root.')
    delete.set_defaults(func=handlers['delete'], agent_command='automation')

    run = commands.add_parser('run', help='Run an automation immediately.')
    run.add_argument('automation_id')
    run.add_argument('--root', default='.', help='Workspace root.')
    run.set_defaults(func=handlers['run'], agent_command='automation')

    tick = commands.add_parser('tick', help='Run all due automations once.')
    tick.add_argument('--root', default='.', help='Workspace root.')
    tick.add_argument(
        '--dry-run',
        action='store_true',
        help='List due automations without starting background runs.',
    )
    tick.set_defaults(func=handlers['tick'], agent_command='automation')

    serve = commands.add_parser(
        'serve', help='Run periodic automation ticks in a lightweight loop.'
    )
    serve.add_argument('--root', default='.', help='Workspace root.')
    serve.add_argument('--interval-seconds', type=float, default=30.0)
    serve.add_argument(
        '--max-ticks',
        type=int,
        default=0,
        help='Stop after N ticks (0 means run forever).',
    )
    serve.set_defaults(func=handlers['serve'], agent_command='automation')


def _add_automation_v2_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '--allowed-toolset',
        action='append',
        default=[],
        metavar='NAME',
        help='Explicit allowed toolset (repeatable). Defaults from --permission-mode.',
    )
    parser.add_argument(
        '--requires-subagent',
        action='store_true',
        help='Record that this automation expects subagent delegation.',
    )
    parser.add_argument(
        '--max-cost-cents',
        type=int,
        default=0,
        help='Per-tick spend cap in cents (0 means unset).',
    )
    parser.add_argument(
        '--max-runtime-seconds',
        type=int,
        default=0,
        help='Per-tick wall-clock cap in seconds (0 means unset).',
    )
    parser.add_argument(
        '--delivery',
        choices=['background_log', 'webhook', 'none'],
        default='background_log',
        help='Where automation output is delivered.',
    )
    parser.add_argument(
        '--context-from',
        default='',
        help='Upstream automation id whose handoff is injected into the agent task.',
    )


def _runs(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
    *,
    top_level: bool = False,
) -> None:
    help_text = 'Inspect persisted agent runs.'
    if top_level:
        help_text = 'Inspect persisted agent runs (alias for agent runs).'
    p = subs.add_parser('runs', help=help_text)
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum runs to list (list subcommand / default action).',
    )
    run_subs = p.add_subparsers(dest='runs_command')

    list_p = run_subs.add_parser('list', help='List persisted runs.')
    list_p.add_argument('--limit', type=int, default=20)
    list_p.set_defaults(func=handlers['list'])

    show_p = run_subs.add_parser('show', help='Show run JSONL events.')
    show_p.add_argument('run_id')
    show_p.set_defaults(func=handlers['show'])

    trace_p = run_subs.add_parser('trace', help='Show run audit timeline.')
    trace_p.add_argument('run_id')
    trace_p.add_argument(
        '--text',
        action='store_true',
        help='Print human-readable timeline instead of JSON.',
    )
    trace_p.set_defaults(func=handlers['trace'])

    export_p = run_subs.add_parser('export', help='Export run trace and completeness.')
    export_p.add_argument('run_id')
    export_p.set_defaults(func=handlers['export'])

    replay_p = run_subs.add_parser(
        'replay', help='Dry-run replay of tool/approval chain (no re-execution).'
    )
    replay_p.add_argument('run_id')
    replay_p.set_defaults(func=handlers['replay'])

    defaults: dict[str, object] = {'func': handlers['list'], 'runs_command': 'list'}
    if top_level:
        defaults['command'] = 'runs'
    p.set_defaults(**defaults)


def _show(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser('show', help='Show one persisted run JSONL record.')
    p.add_argument('run_id', help='Run id to show.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.set_defaults(func=handler)


def _card(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'card',
        help='Print an AgentCard describing this agent and its registered tools.',
    )
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument(
        '--agent-name',
        default='teaagent',
        help='Agent name to embed in the card. Default: teaagent.',
    )
    p.add_argument(
        '--endpoint',
        default=None,
        help='Public endpoint URL to embed in the card (optional).',
    )
    p.set_defaults(func=handler)


def _subagent_review(
    subs: argparse._SubParsersAction,
    handlers: dict[str, Callable],  # type: ignore[type-arg]
) -> None:
    p = subs.add_parser(
        'subagent-review',
        help='Inspect and apply isolated subagent review patches.',
    )
    commands = p.add_subparsers(dest='subagent_review_command', required=True)

    list_cmd = commands.add_parser('list', help='List subagent review artifacts.')
    list_cmd.add_argument('--root', default='.', help='Workspace root.')
    list_cmd.add_argument('--parent-run-id', default=None)
    list_cmd.set_defaults(func=handlers['list'])

    show = commands.add_parser('show', help='Show one subagent review artifact.')
    show.add_argument('review_id')
    show.add_argument('--root', default='.', help='Workspace root.')
    show.add_argument('--parent-run-id', default=None)
    show.set_defaults(func=handlers['show'])

    check = commands.add_parser(
        'check', help='Check whether a review patch applies cleanly.'
    )
    check.add_argument('review_id')
    check.add_argument('--root', default='.', help='Workspace root.')
    check.add_argument('--parent-run-id', default=None)
    check.set_defaults(func=handlers['check'])

    apply = commands.add_parser(
        'apply', help='Apply one reviewed subagent patch with git apply --3way.'
    )
    apply.add_argument('review_id')
    apply.add_argument('--root', default='.', help='Workspace root.')
    apply.add_argument('--parent-run-id', default=None)
    apply.set_defaults(func=handlers['apply'])
