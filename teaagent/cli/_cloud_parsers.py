"""CLI argument parsers for ``teaagent cloud`` subcommands."""

from __future__ import annotations

from typing import Any


def register(
    subparsers: Any,
    handlers: dict[str, Any],
) -> None:
    parser = subparsers.add_parser(
        'cloud',
        help='Cloud/managed runtime task lifecycle (submit, list, show, cancel, capabilities).',
    )
    cloud_sub = parser.add_subparsers(dest='cloud_command', required=True)

    p_submit = cloud_sub.add_parser(
        'submit', help='Submit a task to a managed runtime.'
    )
    p_submit.add_argument('name', help='Task name for identification.')
    p_submit.add_argument('task', help='Task prompt to execute.')
    p_submit.add_argument(
        '--runtime',
        default='anthropic',
        help='Runtime backend (anthropic, openai, ...).',
    )
    p_submit.add_argument('--json', action='store_true', help='Output as JSON.')
    p_submit.add_argument('--root', default='.', help='Workspace root directory.')
    p_submit.set_defaults(func=handlers['submit'])

    p_list = cloud_sub.add_parser('list', help='List cloud tasks.')
    p_list.add_argument(
        '--status',
        default=None,
        help='Filter by status (pending/running/completed/failed).',
    )
    p_list.add_argument('--limit', type=int, default=50, help='Max results.')
    p_list.add_argument('--json', action='store_true', help='Output as JSON.')
    p_list.add_argument('--root', default='.', help='Workspace root directory.')
    p_list.set_defaults(func=handlers['list'])

    p_show = cloud_sub.add_parser('show', help='Show cloud task details.')
    p_show.add_argument('task_id', help='Task ID.')
    p_show.add_argument('--json', action='store_true', help='Output as JSON.')
    p_show.add_argument('--root', default='.', help='Workspace root directory.')
    p_show.set_defaults(func=handlers['show'])

    p_cancel = cloud_sub.add_parser('cancel', help='Cancel a cloud task.')
    p_cancel.add_argument('task_id', help='Task ID to cancel.')
    p_cancel.add_argument('--root', default='.', help='Workspace root directory.')
    p_cancel.set_defaults(func=handlers['cancel'])

    p_caps = cloud_sub.add_parser(
        'capabilities', help='List available managed runtime capabilities.'
    )
    p_caps.add_argument('--json', action='store_true', help='Output as JSON.')
    p_caps.add_argument('--root', default='.', help='Workspace root directory.')
    p_caps.set_defaults(func=handlers['capabilities'])
