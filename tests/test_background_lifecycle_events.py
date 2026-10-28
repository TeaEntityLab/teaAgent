# test-type: lifecycle
"""ADR-0032 Amendment A1: background lifecycle events on a dedicated chain.

Submit and stop transitions are appended to
``<BackgroundRunStore.dir>/lifecycle-<sha256(workspace root)[:12]>.jsonl``
through ``AuditLogger`` (one chain and HMAC key per workspace). The envelope ``run_id`` is ``background:<background_id>``.
Payload keys are the exact A1.2 tables; the command is recorded as a digest only.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest

from teaagent.audit import AuditLogger
from teaagent.audit_chain import verify_audit_chain
from teaagent.ergonomics import background_run
from teaagent.ergonomics.background_run import BackgroundRunStore
from teaagent.errors import AuditDurabilityError
from teaagent.run_evidence import build_run_evidence_bundle
from teaagent.run_store import RunStore

_DEAD_PID = 2_147_483_645
_SLEEP_CHILD = [sys.executable, '-c', 'import time; time.sleep(60)']
_EXIT_CHILD = [sys.executable, '-c', 'pass']
_SUBMIT_KEYS = {
    'background_id',
    'child_run_id',
    'pid',
    'started_at',
    'command_digest',
    'label',
}
_STOP_KEYS = {
    'background_id',
    'child_run_id',
    'pid',
    'stop_signal',
    'stopped_at',
    'exit_code',
    'exit_code_derived',
}


def _lifecycle_path(store: BackgroundRunStore) -> Path:
    return background_run.lifecycle_log_path(store.root, directory=store.dir)


def _lifecycle_rows(store: BackgroundRunStore) -> list[dict[str, Any]]:
    path = _lifecycle_path(store)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def _seed_dead_record(
    store: BackgroundRunStore, background_id: str, run_id: str | None = None
) -> Path:
    log_path = store.dir / f'{background_id}.log'
    log_path.write_text('', encoding='utf-8')
    record: dict[str, Any] = {
        'background_id': background_id,
        'pid': _DEAD_PID,
        'command': ['noop', 'SEEDED-TASK-TEXT'],
        'started_at': '2026-10-27T00:00:00+00:00',
        'log_path': str(log_path),
    }
    if run_id is not None:
        record['run_id'] = run_id
    record_path = store.dir / f'{background_id}.json'
    record_path.write_text(json.dumps(record), encoding='utf-8')
    return record_path


def _seed_run(root: Path, run_id: str, terminal: str) -> None:
    runs_dir = root / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            'event_type': 'run_started',
            'run_id': run_id,
            'timestamp': '2026-10-27T00:00:00+00:00',
            'payload': {},
        },
        {
            'event_type': terminal,
            'run_id': run_id,
            'timestamp': '2026-10-27T00:00:01+00:00',
            'payload': {},
        },
    ]
    (runs_dir / f'{run_id}.jsonl').write_text(
        '\n'.join(json.dumps(line) for line in lines) + '\n', encoding='utf-8'
    )


def test_start_emits_background_submitted_after_record_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The submit event is written only after the record file exists."""
    store = BackgroundRunStore(tmp_path)
    observed: list[tuple[str, bool]] = []
    original = AuditLogger.record

    def spy(self: AuditLogger, event_type: str, run_id: str, **payload: Any) -> Any:
        background_id = run_id.removeprefix('background:')
        observed.append((event_type, store._record_path(background_id).is_file()))
        return original(self, event_type, run_id, **payload)

    monkeypatch.setattr(AuditLogger, 'record', spy)
    record = store.start(_SLEEP_CHILD)
    try:
        assert observed == [('background_submitted', True)]
        rows = _lifecycle_rows(store)
        assert [row['event_type'] for row in rows] == ['background_submitted']
        assert rows[0]['payload']['background_id'] == record.background_id
    finally:
        store.stop(record.background_id, timeout_seconds=5)


def test_submitted_payload_keys_are_exact(tmp_path: Path) -> None:
    """background_submitted carries exactly the A1.2 keys and nothing else."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD, label='exact-keys')
    try:
        (row,) = _lifecycle_rows(store)
        assert set(row['payload']) == _SUBMIT_KEYS
        assert row['payload']['pid'] == record.pid
        assert row['payload']['started_at'] == record.started_at
        assert row['payload']['label'] == 'exact-keys'
    finally:
        store.stop(record.background_id, timeout_seconds=5)


def test_submitted_run_id_is_null_at_submit(tmp_path: Path) -> None:
    """The child mints its run id later, so submit never carries one."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD)
    try:
        assert record.run_id is None
        (row,) = _lifecycle_rows(store)
        assert row['payload']['child_run_id'] is None
    finally:
        store.stop(record.background_id, timeout_seconds=5)


_TASK_SENTINEL = 'TASK-SENTINEL-7f3a9c'


def test_command_digest_is_sha256_of_argv_and_excludes_task_text(
    tmp_path: Path,
) -> None:
    """command_digest is sha256 of json.dumps(argv); the task text is not written."""
    store = BackgroundRunStore(tmp_path)
    argv = [*_SLEEP_CHILD, _TASK_SENTINEL]
    record = store.start(argv)
    try:
        expected = hashlib.sha256(json.dumps(argv).encode('utf-8')).hexdigest()
        (row,) = _lifecycle_rows(store)
        assert row['payload']['command_digest'] == expected
        assert _TASK_SENTINEL not in _lifecycle_path(store).read_text(encoding='utf-8')
    finally:
        store.stop(record.background_id, timeout_seconds=5)


def test_submitted_payload_has_no_readable_command(tmp_path: Path) -> None:
    """No readable command field exists (owner decision Q3: digest only)."""
    store = BackgroundRunStore(tmp_path)
    argv = [*_SLEEP_CHILD, _TASK_SENTINEL]
    record = store.start(argv)
    try:
        (row,) = _lifecycle_rows(store)
        payload = row['payload']
        assert 'command' not in payload
        assert 'command_summary' not in payload
        for value in payload.values():
            assert _TASK_SENTINEL not in str(value)
    finally:
        store.stop(record.background_id, timeout_seconds=5)


def test_stop_emits_background_stopped_on_first_transition(tmp_path: Path) -> None:
    """The first stop of a live child emits one background_stopped event."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD)
    stopped = store.stop(record.background_id, timeout_seconds=5)

    stop_rows = [
        row
        for row in _lifecycle_rows(store)
        if row['event_type'] == 'background_stopped'
    ]
    assert len(stop_rows) == 1
    payload = stop_rows[0]['payload']
    assert set(payload) == _STOP_KEYS
    assert payload['background_id'] == record.background_id
    assert payload['pid'] == record.pid
    assert payload['stop_signal'] == 'SIGTERM'
    assert payload['stopped_at'] == stopped['stopped_at']
    assert payload['exit_code'] is None
    assert payload['exit_code_derived'] is False
    assert payload['child_run_id'] is None


def test_repeated_stop_emits_no_second_event(tmp_path: Path) -> None:
    """A stop on an already stopped record returns early and emits nothing."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD)
    store.stop(record.background_id, timeout_seconds=5)
    store.stop(record.background_id, timeout_seconds=5)

    events = [row['event_type'] for row in _lifecycle_rows(store)]
    assert events == ['background_submitted', 'background_stopped']


def test_stop_on_dead_process_still_emits_background_stopped(tmp_path: Path) -> None:
    """BG-001 section 3.6: stopping a dead process records the stop without raising."""
    store = BackgroundRunStore(tmp_path)
    _seed_dead_record(store, 'bg-dead-stop')

    stopped = store.stop('bg-dead-stop', timeout_seconds=0)

    (row,) = _lifecycle_rows(store)
    assert row['event_type'] == 'background_stopped'
    assert row['payload']['pid'] == _DEAD_PID
    assert row['payload']['stop_signal'] == 'SIGTERM'
    assert row['payload']['stopped_at'] == stopped['stopped_at']


def test_stopped_exit_code_derived_true_only_for_completed_stand_in(
    tmp_path: Path,
) -> None:
    """exit_code_derived is true only when the U-P1-17 stand-in 0 is used."""
    store = BackgroundRunStore(tmp_path)
    _seed_dead_record(store, 'bg-completed', run_id='run-completed-stop')
    _seed_run(tmp_path, 'run-completed-stop', 'run_completed')

    store.stop('bg-completed', timeout_seconds=0)

    (row,) = _lifecycle_rows(store)
    assert row['payload']['exit_code'] == 0
    assert row['payload']['exit_code_derived'] is True
    persisted = json.loads(
        (store.dir / 'bg-completed.json').read_text(encoding='utf-8')
    )
    assert 'exit_code_derived' not in persisted


def test_stopped_exit_code_null_for_reaped_failed_run(tmp_path: Path) -> None:
    """U-P1-17 regression: a failed run never gets a fabricated exit code."""
    store = BackgroundRunStore(tmp_path)
    _seed_dead_record(store, 'bg-failed', run_id='run-failed-stop')
    _seed_run(tmp_path, 'run-failed-stop', 'run_failed')

    store.stop('bg-failed', timeout_seconds=0)

    (row,) = _lifecycle_rows(store)
    assert row['payload']['exit_code'] is None
    assert row['payload']['exit_code_derived'] is False


def test_envelope_run_id_is_background_namespace_and_non_empty(tmp_path: Path) -> None:
    """Every lifecycle envelope carries background:<background_id>."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD)
    store.stop(record.background_id, timeout_seconds=5)

    rows = _lifecycle_rows(store)
    assert len(rows) == 2
    for row in rows:
        assert row['run_id'] == f'background:{record.background_id}'
        assert row['run_id']


def test_envelope_run_id_never_collides_with_minted_run_ids(tmp_path: Path) -> None:
    """Minted run ids are bare uuid4 hex, so the background namespace cannot clash."""
    import re
    from uuid import uuid4

    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD)
    try:
        envelope = f'background:{record.background_id}'
        assert re.fullmatch(r'[0-9a-f]{32}', uuid4().hex)
        assert not re.fullmatch(r'[0-9a-f]{32}', envelope)
        assert not RunStore(tmp_path).run_exists(envelope)
    finally:
        store.stop(record.background_id, timeout_seconds=5)


def test_lifecycle_chain_verifies_strict_with_submit_and_stop_from_two_loggers(
    tmp_path: Path,
) -> None:
    """Submit and stop written by two stores still form one strict hash chain."""
    submitter = BackgroundRunStore(tmp_path)
    stale = AuditLogger(path=_lifecycle_path(submitter))
    record = submitter.start(_SLEEP_CHILD)
    stopper = BackgroundRunStore(tmp_path)
    stopper.stop(record.background_id, timeout_seconds=5)

    path = _lifecycle_path(submitter)
    result = verify_audit_chain(path, secret_key=stale.get_chain_key(), strict=True)
    assert result.valid, result.error
    assert result.event_count == 2
    assert result.total_prev_hash_mismatches == 0


def test_readonly_store_emits_nothing(tmp_path: Path) -> None:
    """A readonly store persists nothing, so it emits nothing."""
    writable = BackgroundRunStore(tmp_path)
    _seed_dead_record(writable, 'bg-readonly')

    readonly = BackgroundRunStore(tmp_path, readonly=True)
    readonly.stop('bg-readonly', timeout_seconds=0)

    assert not _lifecycle_path(writable).exists()


def test_record_persist_failure_emits_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the record cannot be persisted, no lifecycle event is written."""
    store = BackgroundRunStore(tmp_path)

    def fail_write(*_args: Any, **_kwargs: Any) -> None:
        raise OSError('simulated disk full')

    monkeypatch.setattr(background_run, 'atomic_write_text', fail_write)
    with pytest.raises(OSError, match='simulated disk full'):
        store.start(_EXIT_CHILD)
    assert _lifecycle_rows(store) == []

    _seed_dead_record(store, 'bg-persist-stop')
    monkeypatch.setattr(background_run, '_persist_record_state', fail_write)
    with pytest.raises(OSError, match='simulated disk full'):
        store.stop('bg-persist-stop', timeout_seconds=0)
    assert _lifecycle_rows(store) == []


def _block_lifecycle_file(store: BackgroundRunStore) -> None:
    # A directory where the chain file must be makes every append fail.
    _lifecycle_path(store).mkdir(parents=True)


def test_emit_failure_compliance_mode_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In compliance mode a failed emit raises after the record is persisted."""
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '1')
    store = BackgroundRunStore(tmp_path)
    _block_lifecycle_file(store)

    with pytest.raises(AuditDurabilityError):
        store.start(_EXIT_CHILD)
    assert list(store.dir.glob('*.json')), 'record must be persisted before emit'


def test_emit_failure_outside_compliance_logs_and_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Outside compliance mode a failed emit is logged at ERROR and not retried."""
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '0')
    store = BackgroundRunStore(tmp_path)
    _block_lifecycle_file(store)

    attempts: list[str] = []
    original = AuditLogger.record

    def counting(
        self: AuditLogger, event_type: str, run_id: str, **payload: Any
    ) -> Any:
        attempts.append(event_type)
        return original(self, event_type, run_id, **payload)

    monkeypatch.setattr(AuditLogger, 'record', counting)
    with caplog.at_level(logging.ERROR, logger=background_run.logger.name):
        record = store.start(_EXIT_CHILD)

    assert record.background_id
    assert attempts == ['background_submitted']
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any(record.background_id in r.getMessage() for r in errors)


def test_tenant_scoped_lifecycle_path_under_tenant_dir(tmp_path: Path) -> None:
    """A tenant store writes its lifecycle chain under its tenant background dir."""
    store = BackgroundRunStore(tmp_path, tenant_id='acme')
    record = store.start(_SLEEP_CHILD)
    try:
        expected = tmp_path / '.teaagent' / 'tenants' / 'acme' / 'background'
        expected = background_run.lifecycle_log_path(tmp_path, directory=expected)
        assert expected.is_file()
        assert _lifecycle_path(store) == expected
    finally:
        store.stop(record.background_id, timeout_seconds=5)


def test_run_evidence_fold_unchanged_without_background_events(tmp_path: Path) -> None:
    """Run evidence is identical before and after background submit and stop."""
    run_id = 'run-evidence-golden'
    _seed_run(tmp_path, run_id, 'run_completed')
    before = build_run_evidence_bundle(tmp_path, run_id)

    store = BackgroundRunStore(tmp_path)
    record = store.start(_SLEEP_CHILD)
    store.stop(record.background_id, timeout_seconds=5)
    assert _lifecycle_path(store).is_file()

    after = build_run_evidence_bundle(tmp_path, run_id)
    assert repr(after) == repr(before)
    for path in (tmp_path / '.teaagent').rglob('*.jsonl'):
        if path.name.startswith('lifecycle-'):
            continue
        assert 'background_' not in path.read_text(encoding='utf-8')


def test_lifecycle_file_is_per_workspace(tmp_path: Path) -> None:
    """Each workspace root gets its own chain file; the same root keeps its name."""
    root_a = tmp_path / 'workspace-a'
    root_b = tmp_path / 'workspace-b'
    root_a.mkdir()
    root_b.mkdir()
    name_a = background_run.lifecycle_log_path(root_a, directory=tmp_path).name
    name_b = background_run.lifecycle_log_path(root_b, directory=tmp_path).name
    assert name_a != name_b
    assert name_a == background_run.lifecycle_log_path(root_a, directory=tmp_path).name
    expected_hash = hashlib.sha256(str(root_a.resolve()).encode('utf-8')).hexdigest()
    assert name_a == f'lifecycle-{expected_hash[:12]}.jsonl'


def test_no_private_auditlogger_override() -> None:
    """background_run defines no AuditLogger subclass (no private hook)."""
    own_subclasses = [
        obj
        for _, obj in inspect.getmembers(background_run, inspect.isclass)
        if obj.__module__ == background_run.__name__
        and issubclass(obj, AuditLogger)
        and obj is not AuditLogger
    ]
    assert own_subclasses == []
    assert not hasattr(background_run, '_LifecycleAuditLogger')
