from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    memory = subparsers.add_parser('memory', help='Manage local workspace memory.')
    subs = memory.add_subparsers(dest='memory_command', required=True)

    add = subs.add_parser('add', help='Add one memory entry.')
    add.add_argument('content', help='Memory content to store.')
    add.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    add.add_argument(
        '--tag', action='append', default=[], help='Tag to attach. Can be repeated.'
    )
    add.add_argument(
        '--write-source',
        choices=['local', 'agent_run', 'web_message'],
        default='local',
        help='Provenance source for this memory write (web_message quarantines unless attested).',
    )
    add.add_argument(
        '--i-attest-untrusted-write',
        action='store_true',
        help='One-shot owner attestation after reviewing an untrusted web/message payload.',
    )
    add.set_defaults(func=handlers['add'])

    lst = subs.add_parser('list', help='List recent memory entries.')
    lst.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    lst.add_argument('--limit', type=int, default=20, help='Maximum memories to list.')
    lst.set_defaults(func=handlers['list'])

    search = subs.add_parser('search', help='Search memory entries.')
    search.add_argument('query', help='Search query.')
    search.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    search.add_argument(
        '--limit', type=int, default=10, help='Maximum memories to return.'
    )
    search.set_defaults(func=handlers['search'])

    show = subs.add_parser('show', help='Show one memory entry.')
    show.add_argument('memory_id', help='Memory id to show.')
    show.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    show.set_defaults(func=handlers['show'])

    failures = subs.add_parser('failures', help='Failure experience cards.')
    fail_subs = failures.add_subparsers(dest='failures_command', required=True)

    fail_list = fail_subs.add_parser('list', help='List failure cards.')
    fail_list.add_argument('--root', default='.', help='Workspace root.')
    fail_list.add_argument(
        '--active-only', action='store_true', help='Hide expired/invalidated cards.'
    )
    fail_list.set_defaults(func=handlers['failures_list'])

    fail_show = fail_subs.add_parser('show', help='Show one failure card.')
    fail_show.add_argument('card_id')
    fail_show.add_argument('--root', default='.', help='Workspace root.')
    fail_show.set_defaults(func=handlers['failures_show'])

    fail_invalidate = fail_subs.add_parser(
        'invalidate', help='Invalidate a failure card.'
    )
    fail_invalidate.add_argument('card_id')
    fail_invalidate.add_argument('--root', default='.', help='Workspace root.')
    fail_invalidate.add_argument('--reason', required=True, help='Invalidation reason.')
    fail_invalidate.set_defaults(func=handlers['failures_invalidate'])

    fail_prune = fail_subs.add_parser('prune', help='Remove expired/invalidated cards.')
    fail_prune.add_argument('--root', default='.', help='Workspace root.')
    fail_prune.set_defaults(func=handlers['failures_prune'])
