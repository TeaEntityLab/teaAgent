from __future__ import annotations

from teaagent.ergonomics.human_output import (
    build_readiness_items,
    format_readiness_summary,
    format_setup_summary,
)


def test_build_readiness_items_categorizes_git_permission_as_blocking() -> None:
    payload = {
        'dry_run': True,
        'provider': 'gpt',
        'preflight': {
            'ready': False,
            'health': {
                'healthy': False,
                'failures': ['Permission denied: Cannot write to /repo/.git'],
                'warnings': [],
            },
        },
        'would_invoke_model': False,
    }
    items = build_readiness_items(payload, root='/repo')
    assert any(i.level == 'blocking' for i in items)
    assert any(i.next_command for i in items)


def test_format_readiness_summary_includes_ready_and_next() -> None:
    payload = {
        'ready': True,
        'provider': 'gpt',
        'task': 'summarize tests',
        'token_budget': {'usage_level': 'low'},
        'recommendations': [
            {
                'command': 'teaagent run "summarize tests" --permission-mode read-only',
                'reason': 'safe',
            }
        ],
    }
    text = format_readiness_summary(payload, root='.')
    assert 'Ready: yes' in text
    assert 'gpt' in text
    assert 'teaagent run' in text


def test_format_setup_summary_lists_safe_command() -> None:
    payload = {
        'ok': True,
        'root': '/tmp/ws',
        'configured': {'provider': 'gpt', 'permission_mode': 'read-only'},
        'safe_command': 'teaagent daily "readiness" --dry-run --root /tmp/ws',
        'next_steps': ['teaagent recipes list'],
    }
    text = format_setup_summary(payload)
    assert 'Status: ok' in text
    assert 'Try next:' in text
    assert 'teaagent daily' in text


def test_format_ascii_table() -> None:
    from teaagent.ergonomics.human_output import format_ascii_table

    headers = ['Name', 'Age']
    keys = ['name', 'age']
    rows = [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25},
    ]
    tbl = format_ascii_table(headers, rows, keys)
    assert 'Alice' in tbl
    assert 'Bob' in tbl
    assert 'Age' in tbl
