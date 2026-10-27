# test-type: behavior
"""Pin the owner-ratified pending-approval TTL auto-deny (dogfood G16).

A pending approval older than TEAAGENT_PENDING_APPROVAL_TTL_SECONDS (default
24h) is auto-denied: the lookup returns None, records a single
``tool_call_denied`` with ``reason_code='expired'``, and the pending view
collector omits it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from teaagent.approval.selectors import collect_pending_approval_views
from teaagent.ergonomics._approval_grants import (
    PENDING_APPROVAL_TTL_SECONDS,
    get_pending_approval_ttl_seconds,
)
from teaagent.run_store import RunStore

TTL_ENV = 'TEAAGENT_PENDING_APPROVAL_TTL_SECONDS'
CALL_ID = 'call-ttl-1'


def _ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _write_paused_run(store: RunStore, run_id: str, created_at: str) -> None:
    """Write a paused run with one unresolved tool_call_pending_approval."""
    events: list[dict[str, Any]] = [
        {
            'event_type': 'run_started',
            'run_id': run_id,
            'created_at': _ago(0),
            'payload': {'task': 'write docs'},
        },
        {
            'event_type': 'tool_call_pending_approval',
            'run_id': run_id,
            'created_at': created_at,
            'payload': {
                'call_id': CALL_ID,
                'tool_name': 'workspace_write_file',
                'arguments': {'path': 'docs/cli.md', 'content': 'x'},
                'reason': 'destructive tool requires approval',
                'reason_code': 'destructive',
                'annotations': {'destructive': True},
            },
        },
    ]
    path = store.run_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n',
        encoding='utf-8',
    )


def _events(store: RunStore, run_id: str, event_type: str) -> list[dict[str, Any]]:
    return [e for e in store.show_run(run_id) if e.get('event_type') == event_type]


def test_expired_pending_approval_is_auto_denied_and_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TTL_ENV, '60')
    store = RunStore(tmp_path)
    _write_paused_run(store, 'run-expired', created_at=_ago(120))

    # The collector is read-only: it omits the expired pending and records nothing.
    assert [v.run_id for v in collect_pending_approval_views(store)] == []
    assert _events(store, 'run-expired', 'tool_call_denied') == []

    # The lookup expires the pending and records the auto-denial.
    assert store.pending_approval_for_run('run-expired') is None

    denials = _events(store, 'run-expired', 'tool_call_denied')
    assert len(denials) == 1
    payload = denials[0]['payload']
    assert payload['call_id'] == CALL_ID
    assert payload['tool_name'] == 'workspace_write_file'
    assert payload['reason_code'] == 'expired'

    assert collect_pending_approval_views(store) == []


def test_fresh_pending_approval_stays_pending_without_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TTL_ENV, '60')
    store = RunStore(tmp_path)
    _write_paused_run(store, 'run-fresh', created_at=_ago(0))

    pending = store.pending_approval_for_run('run-fresh')
    assert pending is not None
    assert pending['call_id'] == CALL_ID

    views = collect_pending_approval_views(store)
    assert [v.run_id for v in views] == ['run-fresh']

    assert _events(store, 'run-fresh', 'tool_call_denied') == []


def test_default_ttl_is_24_hours_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TTL_ENV, raising=False)
    assert PENDING_APPROVAL_TTL_SECONDS == 86400
    assert get_pending_approval_ttl_seconds() == 86400


@pytest.mark.parametrize('raw', ['', 'soon', '1.5', '0', '-5'])
def test_invalid_ttl_env_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(TTL_ENV, raw)
    assert get_pending_approval_ttl_seconds() == 86400


def test_valid_ttl_env_override_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TTL_ENV, '60')
    assert get_pending_approval_ttl_seconds() == 60


def test_default_ttl_boundary_under_24h_pending_and_over_24h_expired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TTL_ENV, raising=False)
    store = RunStore(tmp_path)
    _write_paused_run(store, 'run-under', created_at=_ago(86400 - 600))
    _write_paused_run(store, 'run-over', created_at=_ago(86400 + 600))

    assert store.pending_approval_for_run('run-under') is not None
    assert _events(store, 'run-under', 'tool_call_denied') == []

    assert store.pending_approval_for_run('run-over') is None
    assert len(_events(store, 'run-over', 'tool_call_denied')) == 1


def test_repeated_lookup_on_expired_pending_records_one_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(TTL_ENV, '60')
    store = RunStore(tmp_path)
    _write_paused_run(store, 'run-twice', created_at=_ago(120))

    assert store.pending_approval_for_run('run-twice') is None
    assert store.pending_approval_for_run('run-twice') is None

    assert len(_events(store, 'run-twice', 'tool_call_denied')) == 1
    assert collect_pending_approval_views(store) == []
