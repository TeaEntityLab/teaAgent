from __future__ import annotations

import argparse
from typing import Callable

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    _yesterday(subparsers, handlers['yesterday'])
    _recall(subparsers, handlers['recall'])
    _status_short(subparsers, handlers['status_short'])
    _background(
        subparsers,
        {
            'background_list': handlers['background_list'],
            'background_show': handlers['background_show'],
        },
    )
    _session(subparsers, handlers)
    _recipes(subparsers, handlers)
    _approval(subparsers, handlers)
    _guidance(subparsers, handlers['guidance'])
    _ci(subparsers, handlers['ci_review'])
    _watch(subparsers, handlers['watch'])
    _journal(subparsers, handlers['daily_journal'])


def _yesterday(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'yesterday', help='List audit runs from the previous calendar day.'
    )
    p.add_argument('--root', default='.', help='Workspace root.')
    p.add_argument('--limit', type=int, default=20)
    p.set_defaults(func=handler, command='yesterday')


def _recall(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser('recall', help='List the most recent audit runs.')
    p.add_argument('--root', default='.', help='Workspace root.')
    p.add_argument('--limit', type=int, default=5)
    p.set_defaults(func=handler, command='recall')


def _status_short(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'status', help='One-line harness status (token pressure, pending approvals).'
    )
    p.add_argument('--root', default='.', help='Workspace root.')
    p.add_argument('--provider', choices=available_providers(), default=None)
    p.add_argument('--model', default=None)
    p.add_argument('--run-id', default=None)
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=None,
    )
    p.set_defaults(func=handler, command='status')


def _background(
    subparsers: argparse._SubParsersAction, handlers: dict[str, Callable]
) -> None:  # type: ignore[type-arg]
    background = subparsers.add_parser(
        'background', help='List detached agent runs started with --background.'
    )
    subs = background.add_subparsers(dest='background_command', required=True)
    lst = subs.add_parser('list')
    lst.add_argument('--root', default='.')
    lst.set_defaults(func=handlers['background_list'], command='background')
    show = subs.add_parser('show')
    show.add_argument('background_id')
    show.add_argument('--root', default='.')
    show.set_defaults(func=handlers['background_show'], command='background')


def _session(
    subparsers: argparse._SubParsersAction, handlers: dict[str, Callable]
) -> None:  # type: ignore[type-arg]
    session = subparsers.add_parser('session', help='Browse and resume persisted runs.')
    subs = session.add_subparsers(dest='session_command', required=True)
    lst = subs.add_parser('list', help='List runs with heartbeat and pending approval.')
    lst.add_argument('--root', default='.')
    lst.add_argument('--limit', type=int, default=20)
    lst.set_defaults(func=handlers['session_list'], command='session')
    show = subs.add_parser('show', help='Show one run with events.')
    show.add_argument('run_id')
    show.add_argument('--root', default='.')
    show.set_defaults(func=handlers['session_show'], command='session')
    resume = subs.add_parser('resume', help='Resume a paused or failed run.')
    resume.add_argument('run_id')
    resume.add_argument('--root', default='.')
    resume.add_argument(
        'provider', nargs='?', choices=available_providers(), default=None
    )
    resume.add_argument('--model', default=None)
    resume.add_argument('--fresh-restart', action='store_true')
    resume.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
    )
    resume.set_defaults(func=handlers['session_resume'], command='session')


def _recipes(
    subparsers: argparse._SubParsersAction, handlers: dict[str, Callable]
) -> None:  # type: ignore[type-arg]
    recipes = subparsers.add_parser(
        'recipes', help='List and run built-in task recipes.'
    )
    subs = recipes.add_subparsers(dest='recipes_command', required=True)
    lst = subs.add_parser('list')
    lst.set_defaults(func=handlers['recipes_list'], command='recipes')
    run = subs.add_parser('run', help='Run a recipe (optionally invoke the agent).')
    run.add_argument('name')
    run.add_argument('--root', default='.')
    run.add_argument('--provider', choices=available_providers(), default=None)
    run.add_argument('--model', default=None)
    run.add_argument('--extra', default='')
    run.add_argument('--print-only', action='store_true')
    run.set_defaults(func=handlers['recipes_run'], command='recipes')


def _approval(
    subparsers: argparse._SubParsersAction, handlers: dict[str, Callable]
) -> None:  # type: ignore[type-arg]
    approval = subparsers.add_parser(
        'approval', help='Manage destructive-tool approval presets.'
    )
    subs = approval.add_subparsers(dest='approval_command', required=True)
    lst = subs.add_parser(
        'list', help='List approval grants and policy evaluation order.'
    )
    lst.add_argument('--root', default='.')
    lst.add_argument(
        '--grants-only',
        action='store_true',
        help='Emit only the grants array (legacy JSON shape for jq/scripts).',
    )
    lst.add_argument(
        '--scoped',
        action='store_true',
        help='Emit only the active scoped approvals.',
    )
    lst.set_defaults(func=handlers['approval_list'], command='approval')
    check = subs.add_parser(
        'check',
        help='Explain whether a tool call would be allowed by current presets.',
    )
    check.add_argument('tool_name')
    check.add_argument('--root', default='.')
    check.add_argument(
        '--permission-mode',
        default=PermissionMode.PROMPT.value,
        choices=[mode.value for mode in PermissionMode],
    )
    check.add_argument('--path', default=None, help='Tool path argument to match.')
    check.add_argument(
        '--command', default=None, help='Shell command argument to match.'
    )
    check.add_argument(
        '--arg',
        action='append',
        default=[],
        help='Tool argument as key=value (repeatable). Overrides --path/--command if keys conflict.',
    )
    check.add_argument(
        '--arguments-json',
        default=None,
        help='Tool arguments as JSON string (for complex nested arguments).',
    )
    check.set_defaults(func=handlers['approval_check'], command='approval')
    explain = subs.add_parser(
        'explain',
        help='Explain why a tool call matches or fails to match approval rules.',
    )
    explain.add_argument('tool_name')
    explain.add_argument('--root', default='.')
    explain.add_argument(
        '--permission-mode',
        default=PermissionMode.PROMPT.value,
        choices=[mode.value for mode in PermissionMode],
    )
    explain.add_argument('--path', default=None, help='Tool path argument to match.')
    explain.add_argument(
        '--command', default=None, help='Shell command argument to match.'
    )
    explain.add_argument(
        '--arg',
        action='append',
        default=[],
        help='Tool argument as key=value (repeatable). Overrides --path/--command if keys conflict.',
    )
    explain.add_argument(
        '--arguments-json',
        default=None,
        help='Tool arguments as JSON string (for complex nested arguments).',
    )
    explain.set_defaults(func=handlers['approval_explain'], command='approval')
    revoke = subs.add_parser('revoke', help='Remove one approval grant by grant_id.')
    revoke.add_argument('grant_id')
    revoke.add_argument('--root', default='.')
    revoke.set_defaults(func=handlers['approval_revoke'], command='approval')
    grant = subs.add_parser('grant')
    grant.add_argument('tool_name')
    grant.add_argument('--root', default='.')
    grant.add_argument(
        '--scope', choices=['once', 'session', 'always', 'deny'], default='session'
    )
    grant.add_argument('--permission-mode', default=None)
    grant.add_argument(
        '--path-glob',
        action='append',
        default=[],
        help=(
            'Match tool path argument to this glob (repeatable). With --scope deny, '
            'blocks only matching paths.'
        ),
    )
    grant.add_argument(
        '--command-prefix',
        action='append',
        default=[],
        help=(
            'Match shell command prefix (repeatable). With --scope deny, blocks only '
            'matching commands.'
        ),
    )
    grant.add_argument(
        '--ttl-hours',
        type=float,
        default=None,
        help='Grant expiry in hours (session grants default to 8h when omitted).',
    )
    grant.set_defaults(func=handlers['approval_grant'], command='approval')
    deny = subs.add_parser(
        'deny', help='Deny a tool globally (use grant --scope deny for scoped deny).'
    )
    deny.add_argument('tool_name')
    deny.add_argument('--root', default='.')
    deny.add_argument(
        '--path-glob',
        action='append',
        default=[],
        help='Deny only when the tool path matches this glob (repeatable).',
    )
    deny.add_argument(
        '--command-prefix',
        action='append',
        default=[],
        help='Deny only when the shell command starts with this prefix (repeatable).',
    )
    deny.set_defaults(func=handlers['approval_deny'], command='approval')
    audit = subs.add_parser('audit')
    audit.add_argument('--root', default='.')
    audit.add_argument('--limit', type=int, default=20)
    audit.add_argument(
        '--scoped',
        action='store_true',
        help='Show only audit events related to scoped approvals.',
    )
    audit.set_defaults(func=handlers['approval_audit'], command='approval')
    pending = subs.add_parser(
        'pending', help='List runs with pending approval requests.'
    )
    pending.add_argument('--root', default='.')
    pending.add_argument('--limit', type=int, default=20)
    pending.set_defaults(func=handlers['approval_pending'], command='approval')
    approve = subs.add_parser(
        'approve', help='Approve a pending call and optionally resume the run.'
    )
    approve.add_argument('call_id')
    approve.add_argument('--root', default='.')
    approve.add_argument(
        '--resume', action='store_true', help='Resume the run after approval.'
    )
    approve.set_defaults(func=handlers['approval_approve'], command='approval')
    preset = subs.add_parser(
        'preset', help='Apply a predefined approval policy template.'
    )
    preset.add_argument('name', choices=['dev-safe', 'ci-safe', 'strict'])
    preset.add_argument('--root', default='.')
    preset.set_defaults(func=handlers['approval_preset'], command='approval')
    doctor = subs.add_parser(
        'doctor', help='Diagnose approval policy health and suggest improvements.'
    )
    doctor.add_argument('--root', default='.')
    doctor.add_argument(
        '--prune-expired',
        action='store_true',
        help='Remove expired grants automatically.',
    )
    doctor.add_argument(
        '--fix-duplicates',
        action='store_true',
        help='Remove duplicate grants automatically.',
    )
    doctor.add_argument(
        '--fix-security',
        action='store_true',
        help='Repair .teaagent/ directory and file permissions (0700/0600) automatically.',
    )
    doctor.add_argument(
        '--repair-store',
        action='store_true',
        help='Rebuild approvals.json from corrupt state (backs up corrupt file first). Only repairs if corrupt.',
    )
    doctor.add_argument(
        '--force-reset-store',
        action='store_true',
        help='Reset approvals.json after making a backup even when it validates. Intended for explicit operator recovery.',
    )
    doctor.set_defaults(func=handlers['approval_doctor'], command='approval')
    next_cmd = subs.add_parser(
        'next', help='Show next pending approval and suggest actions.'
    )
    next_cmd.add_argument('--root', default='.')
    next_cmd.set_defaults(func=handlers['approval_next'], command='approval')

    subagents = subs.add_parser(
        'subagents',
        help='Centralized destructive-tool approvals from parallel subagents.',
    )
    subagent_subs = subagents.add_subparsers(
        dest='approval_subagents_command', required=True
    )
    sub_list = subagent_subs.add_parser(
        'list', help='List pending subagent approval requests.'
    )
    sub_list.add_argument('--root', default='.')
    sub_list.add_argument(
        '--parent-run-id',
        default=None,
        help='Filter to one parent run (omit to list all active queues).',
    )
    sub_list.set_defaults(func=handlers['approval_subagents_list'], command='approval')

    sub_approve = subagent_subs.add_parser(
        'approve', help='Approve one queued subagent tool request.'
    )
    sub_approve.add_argument('request_id')
    sub_approve.add_argument('--root', default='.')
    sub_approve.add_argument('--parent-run-id', required=True)
    sub_approve.set_defaults(
        func=handlers['approval_subagents_approve'], command='approval'
    )

    sub_deny = subagent_subs.add_parser(
        'deny', help='Deny one queued subagent tool request.'
    )
    sub_deny.add_argument('request_id')
    sub_deny.add_argument('--root', default='.')
    sub_deny.add_argument('--parent-run-id', required=True)
    sub_deny.add_argument('--reason', default=None)
    sub_deny.set_defaults(func=handlers['approval_subagents_deny'], command='approval')

    sub_approve_all = subagent_subs.add_parser(
        'approve-all', help='Approve all pending requests for a parent run.'
    )
    sub_approve_all.add_argument('--root', default='.')
    sub_approve_all.add_argument('--parent-run-id', required=True)
    sub_approve_all.set_defaults(
        func=handlers['approval_subagents_approve_all'], command='approval'
    )

    sub_deny_all = subagent_subs.add_parser(
        'deny-all', help='Deny all pending requests for a parent run.'
    )
    sub_deny_all.add_argument('--root', default='.')
    sub_deny_all.add_argument('--parent-run-id', required=True)
    sub_deny_all.add_argument('--reason', default=None)
    sub_deny_all.set_defaults(
        func=handlers['approval_subagents_deny_all'], command='approval'
    )

    sub_prune = subagent_subs.add_parser(
        'prune',
        help='Remove stale approval queue files with no pending requests.',
    )
    sub_prune.add_argument('--root', default='.')
    sub_prune.add_argument(
        '--max-age-hours',
        type=float,
        default=168.0,
        help='Delete resolved queue files older than this many hours (default 168).',
    )
    sub_prune.set_defaults(
        func=handlers['approval_subagents_prune'], command='approval'
    )


def _guidance(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'guidance', help='List workspace guidance files (AGENTS.md convention).'
    )
    p.add_argument('--root', default='.')
    p.set_defaults(func=handler, command='guidance')


def _ci(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    ci = subparsers.add_parser('ci', help='CI-oriented harness commands.')
    subs = ci.add_subparsers(dest='ci_command', required=True)
    review = subs.add_parser(
        'review', help='Review staged git diff (read-only recipe).'
    )
    review.add_argument('--root', default='.')
    review.add_argument('--provider', choices=available_providers(), default=None)
    review.add_argument('--model', default=None)
    review.add_argument('--print-only', action='store_true')
    review.add_argument('--diff-only', action='store_true')
    review.add_argument('--max-bytes', type=int, default=120_000)
    review.set_defaults(func=handler, command='ci')


def _watch(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser('watch', help='Poll compact status on an interval.')
    p.add_argument('--root', default='.')
    p.add_argument('--interval', type=float, default=30.0)
    p.add_argument('--provider', choices=available_providers(), default=None)
    p.set_defaults(func=handler, command='watch')


def _journal(subparsers: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        'journal', help='Write today daily markdown journal under .teaagent/daily/.'
    )
    p.add_argument('--root', default='.')
    p.add_argument('provider', nargs='?', default=None, metavar='provider')
    p.add_argument('--task', default=None)
    p.add_argument('--model', default=None)
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
    )
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
    )
    p.set_defaults(func=handler, command='journal')
