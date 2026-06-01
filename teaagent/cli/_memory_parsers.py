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
    fail_list.add_argument(
        '--confidence-filter',
        choices=['low', 'medium', 'high'],
        help='Filter by confidence level.',
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

    fail_auto = fail_subs.add_parser(
        'auto-invalidate', help='Apply automated invalidation rules.'
    )
    fail_auto.add_argument('--root', default='.', help='Workspace root.')
    fail_auto.set_defaults(func=handlers['failures_auto_invalidate'])

    fail_review = fail_subs.add_parser(
        'review', help='Review active failure cards for curation decisions.'
    )
    fail_review.add_argument('--root', default='.', help='Workspace root.')
    fail_review.add_argument(
        '--limit', type=int, default=10, help='Maximum cards to review.'
    )
    fail_review.set_defaults(func=handlers['failures_review'])

    decisions = subs.add_parser(
        'decisions', help='Persistent decision log.'
    )
    dec_subs = decisions.add_subparsers(dest='decisions_command', required=True)

    dec_list = dec_subs.add_parser('list', help='List all decisions.')
    dec_list.add_argument('--root', default='.', help='Workspace root.')
    dec_list.add_argument(
        '--limit', type=int, default=0, help='Limit to N most recent (0 = all).'
    )
    dec_list.set_defaults(func=handlers['decisions_list'])

    dec_add = dec_subs.add_parser('add', help='Add a decision entry.')
    dec_add.add_argument('decision', help='Decision text.')
    dec_add.add_argument('--reason', required=True, help='Reason for the decision.')
    dec_add.add_argument(
        '--dont-reverse', default='',
        help='Context for when not to reverse this decision.'
    )
    dec_add.add_argument('--root', default='.', help='Workspace root.')
    dec_add.set_defaults(func=handlers['decisions_add'])

    team = subs.add_parser('team', help='Team-shared memory.')
    team_subs = team.add_subparsers(dest='team_command', required=True)

    team_list = team_subs.add_parser('list', help='List team memory entries.')
    team_list.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    team_list.set_defaults(func=handlers['team_memory_list'])

    team_add = team_subs.add_parser('add', help='Add a team memory entry.')
    team_add.add_argument('entry', help='Memory entry text.')
    team_add.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    team_add.set_defaults(func=handlers['team_memory_add'])
