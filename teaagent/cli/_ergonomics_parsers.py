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
    lst = subs.add_parser('list')
    lst.add_argument('--root', default='.')
    lst.set_defaults(func=handlers['approval_list'], command='approval')
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
        help='Allow only when the tool path argument matches this glob (repeatable).',
    )
    grant.add_argument(
        '--command-prefix',
        action='append',
        default=[],
        help='Allow only when shell command starts with this prefix (repeatable).',
    )
    grant.add_argument(
        '--ttl-hours',
        type=float,
        default=None,
        help='Grant expiry in hours (session grants default to 8h when omitted).',
    )
    grant.set_defaults(func=handlers['approval_grant'], command='approval')
    deny = subs.add_parser('deny')
    deny.add_argument('tool_name')
    deny.add_argument('--root', default='.')
    deny.set_defaults(func=handlers['approval_deny'], command='approval')
    audit = subs.add_parser('audit')
    audit.add_argument('--root', default='.')
    audit.add_argument('--limit', type=int, default=20)
    audit.set_defaults(func=handlers['approval_audit'], command='approval')


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
