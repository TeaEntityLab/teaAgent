"""Regression tests for classified A-P0-2 observability degradation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from teaagent.audit import AuditLogger
from teaagent.audit_export import export_compliance_bundle
from teaagent.cockpit import assess_stale_workspace
from teaagent.preflight import preflight
from teaagent.subagents._cost import build_child_cost_ledger
from teaagent.subagents._hybrid_store_health import HybridStoreHealthMixin
from teaagent.tui.cockpit_data_sources import ApprovalDataSource

_BOUNDED_OBSERVABILITY_MODULES = (
    'teaagent/audit.py',
    'teaagent/audit_chain.py',
    'teaagent/audit_export.py',
    'teaagent/cockpit.py',
    'teaagent/preflight.py',
    'teaagent/tui/cockpit_data_sources.py',
    'teaagent/subagents/_review.py',
    'teaagent/subagents/_approval_queue_hybrid_store.py',
    'teaagent/subagents/_hybrid_store_health.py',
    'teaagent/subagents/_cost.py',
)
_SILENT_EXCEPT = re.compile(
    r'except[^\n]*:\n(?:[ \t]*#[^\n]*\n)*[ \t]+pass\b', re.MULTILINE
)


def _assert_classified(record: logging.LogRecord, *, severity: str) -> None:
    assert getattr(record, 'error_category', None) == 'system'
    assert getattr(record, 'error_severity', None) == severity
    assert getattr(record, 'recovery_hint', None)


def test_bounded_observability_modules_have_no_silent_except_pass() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for relative_path in _BOUNDED_OBSERVABILITY_MODULES:
        source = (root / relative_path).read_text(encoding='utf-8')
        if _SILENT_EXCEPT.search(source):
            offenders.append(relative_path)
    assert offenders == []


def test_audit_history_read_failure_is_classified(tmp_path: Path, caplog) -> None:
    audit_path = tmp_path / 'audit.jsonl'
    audit_path.write_text('{}\n', encoding='utf-8')

    with (
        patch('builtins.open', side_effect=OSError('sensitive audit path')),
        caplog.at_level(logging.ERROR, logger='teaagent.audit'),
    ):
        AuditLogger(path=audit_path)

    record = next(r for r in caplog.records if 'chain state recovery' in r.message)
    _assert_classified(record, severity='high')
    assert 'sensitive audit path' not in record.message


def test_audit_chain_tenant_fallback_is_classified(tmp_path: Path, caplog) -> None:
    from teaagent.audit_chain import _get_tenant_dir_for_path

    with (
        patch('pathlib.Path.resolve', side_effect=OSError('sensitive tenant path')),
        caplog.at_level(logging.WARNING, logger='teaagent.audit_chain'),
    ):
        result = _get_tenant_dir_for_path(tmp_path, 'run-keys')

    assert result.name == 'run-keys'
    record = next(r for r in caplog.records if 'tenant directory' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive tenant path' not in record.message


def test_audit_export_tenant_fallback_is_classified(tmp_path: Path, caplog) -> None:
    from teaagent.audit_export import _get_tenant_dir_for_path

    with (
        patch('pathlib.Path.resolve', side_effect=OSError('sensitive export path')),
        caplog.at_level(logging.WARNING, logger='teaagent.audit_export'),
    ):
        result = _get_tenant_dir_for_path(tmp_path, 'run-keys')

    assert result.name == 'run-keys'
    record = next(r for r in caplog.records if 'tenant directory' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive export path' not in record.message


def test_audit_export_key_read_failure_is_classified(tmp_path: Path, caplog) -> None:
    log_path = tmp_path / 'run-1.jsonl'
    key_path = tmp_path / 'run-1.key'
    key_path.write_bytes(b'x' * 32)
    chain_result = SimpleNamespace(valid=True, event_count=1, error=None)

    with (
        patch('teaagent.audit_export._get_tenant_dir_for_path', return_value=tmp_path),
        patch('pathlib.Path.read_bytes', side_effect=OSError('sensitive key path')),
        patch(
            'teaagent.audit_export.verify_audit_chain', return_value=chain_result
        ) as verify,
        caplog.at_level(logging.ERROR, logger='teaagent.audit_export'),
    ):
        export_compliance_bundle(
            [{'event_type': 'run_started'}],
            log_path=log_path,
        )

    verify.assert_called_once_with(log_path, secret_key=None)
    record = next(r for r in caplog.records if 'chain key read' in r.message)
    _assert_classified(record, severity='high')
    assert 'sensitive key path' not in record.message


def test_cockpit_divergence_parse_failure_is_classified(tmp_path: Path, caplog) -> None:
    git_result = SimpleNamespace(stdout='')
    divergence = SimpleNamespace(stdout='not-a-number still-not-a-number')

    with (
        patch(
            'teaagent.cockpit._run_git',
            side_effect=[git_result, git_result, divergence],
        ),
        patch('teaagent.cockpit._count_quarantine_lines', return_value=0),
        patch('teaagent.cockpit._count_unreviewed_candidates', return_value=0),
        caplog.at_level(logging.WARNING, logger='teaagent.cockpit'),
    ):
        report = assess_stale_workspace(tmp_path)

    assert report.commits_behind == 0
    assert report.commits_ahead == 0
    record = next(r for r in caplog.records if 'divergence output' in r.message)
    _assert_classified(record, severity='low')


def test_preflight_audit_health_failure_is_classified(tmp_path: Path, caplog) -> None:
    audit_path = tmp_path / '.teaagent' / 'runs' / 'run-1' / 'audit.jsonl'
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text('{}\n', encoding='utf-8')

    with (
        patch(
            'teaagent.audit_chain.read_audit_events',
            side_effect=RuntimeError('sensitive audit event'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.preflight'),
    ):
        preflight('review the current tests', root=tmp_path, provider='gpt')

    record = next(r for r in caplog.records if 'audit health check' in r.message)
    _assert_classified(record, severity='high')
    assert 'sensitive audit event' not in record.message


def test_cockpit_memory_failure_is_classified(tmp_path: Path, caplog) -> None:
    source = ApprovalDataSource(tmp_path)

    with (
        patch(
            'teaagent.memory.MemoryCatalog',
            side_effect=RuntimeError('sensitive memory content'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.tui.cockpit_data_sources'),
    ):
        assert source.get_approvals() == []

    record = next(r for r in caplog.records if 'memory approval source' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive memory content' not in record.message


def test_cockpit_quarantine_failure_is_classified(tmp_path: Path, caplog) -> None:
    quarantine_path = tmp_path / '.teaagent' / 'memory-quarantine.jsonl'
    quarantine_path.parent.mkdir(parents=True)
    quarantine_path.write_text('{}\n', encoding='utf-8')
    catalog = MagicMock()
    catalog.list.return_value = []
    source = ApprovalDataSource(tmp_path)

    with (
        patch('teaagent.memory.MemoryCatalog', return_value=catalog),
        patch('pathlib.Path.read_text', side_effect=OSError('sensitive quarantine')),
        caplog.at_level(logging.ERROR, logger='teaagent.tui.cockpit_data_sources'),
    ):
        assert source.get_approvals() == []

    record = next(
        r for r in caplog.records if 'quarantine approval source' in r.message
    )
    _assert_classified(record, severity='medium')
    assert 'sensitive quarantine' not in record.message


def test_cockpit_approval_count_failure_is_classified(tmp_path: Path, caplog) -> None:
    source = ApprovalDataSource(tmp_path)

    with (
        patch(
            'teaagent.memory.MemoryCatalog',
            side_effect=RuntimeError('sensitive approval count'),
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.tui.cockpit_data_sources'),
    ):
        assert source.get_approval_count() == 0

    record = next(r for r in caplog.records if 'approval count source' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive approval count' not in record.message


def test_rollback_cleanup_failure_is_classified(caplog) -> None:
    queue_path = MagicMock()
    queue_path.exists.return_value = True
    queue_path.unlink.side_effect = OSError('sensitive queue path')
    file_store = MagicMock()
    file_store.load.return_value = SimpleNamespace(
        parent_run_id='test-rollback-validation'
    )
    file_store.list_parent_run_ids.return_value = ['test-rollback-validation']
    file_store.queue_path.return_value = queue_path
    subject = SimpleNamespace(_file_store=file_store)

    with caplog.at_level(
        logging.ERROR, logger='teaagent.subagents._hybrid_store_health'
    ):
        result = HybridStoreHealthMixin._validate_rollback(subject)

    assert result['cleanup_operation'] is False
    assert result['overall'] is False
    record = next(r for r in caplog.records if 'validation cleanup' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive queue path' not in record.message


def test_rollback_validation_failure_is_classified_and_redacted(caplog) -> None:
    file_store = MagicMock()
    file_store.save.side_effect = OSError('sensitive approval payload')
    subject = SimpleNamespace(_file_store=file_store)

    with caplog.at_level(
        logging.ERROR, logger='teaagent.subagents._hybrid_store_health'
    ):
        result = HybridStoreHealthMixin._validate_rollback(subject)

    assert result['overall'] is False
    assert result['error'] == 'rollback validation failed'
    assert 'sensitive approval payload' not in str(result)
    record = next(
        r for r in caplog.records if 'rollback validation failed' in r.message
    )
    _assert_classified(record, severity='high')
    assert 'sensitive approval payload' not in record.message


def test_child_cost_event_read_failure_is_classified(tmp_path: Path, caplog) -> None:
    store = MagicMock()
    store.describe_run.return_value = SimpleNamespace(
        cost_cents=5.0,
        input_tokens=10,
        output_tokens=20,
        status='complete',
    )
    store.show_run.side_effect = OSError('sensitive run path')

    with (
        patch('teaagent.run_store.RunStore', return_value=store),
        caplog.at_level(logging.WARNING, logger='teaagent.subagents._cost'),
    ):
        ledger = build_child_cost_ledger(tmp_path, [('run-1', 'child')])

    assert ledger.entries[0].status == 'complete'
    assert ledger.entries[0].tool_calls == 0
    record = next(r for r in caplog.records if 'event count' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive run path' not in record.message


def test_child_cost_run_read_failure_is_classified(tmp_path: Path, caplog) -> None:
    store = MagicMock()
    store.describe_run.side_effect = OSError('sensitive run summary')

    with (
        patch('teaagent.run_store.RunStore', return_value=store),
        caplog.at_level(logging.ERROR, logger='teaagent.subagents._cost'),
    ):
        ledger = build_child_cost_ledger(tmp_path, [('run-1', 'child')])

    assert ledger.entries[0].status == 'not_found'
    record = next(r for r in caplog.records if 'child run summary' in r.message)
    _assert_classified(record, severity='medium')
    assert 'sensitive run summary' not in record.message
