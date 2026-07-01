"""Tests for run evidence summary extraction."""

import tempfile

from run_store_fixtures import write_run_events, write_undo_journal

from teaagent.evidence_summary import (
    RunEvidenceSummary,
    build_evidence_summary,
    summarize_run_events,
)
from teaagent.run_store import RunStore


class TestRunEvidenceSummary:
    def test_empty_run_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'nonexistent-run', tmpdir)
            assert summary.run_id == 'nonexistent-run'
            assert summary.status == 'unknown'
            assert summary.changed_files == []
            assert summary.commands_run == []
            assert summary.tests_executed == 0
            assert summary.approvals == []
            assert summary.total_cost_cents == 0
            assert summary.rollback_available is False
            assert summary.started_at == ''
            assert summary.finished_at is None

    def test_successful_run_summary(self):
        events = [
            {
                'run_id': 'test-success',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-success',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
                'payload': {'cost_cents': 150},
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-success', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-success', tmpdir)
            assert summary.run_id == 'test-success'
            assert summary.status == 'success'
            assert summary.started_at == '2026-06-01T10:00:00Z'
            assert summary.finished_at == '2026-06-01T10:05:00Z'
            assert summary.total_cost_cents == 150

    def test_summary_extracts_file_writes(self):
        events = [
            {
                'run_id': 'test-files',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-files',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {
                    'tool_name': 'workspace_write_file',
                    'arguments': {'path': 'src/main.py'},
                },
            },
            {
                'run_id': 'test-files',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:02:00Z',
                'payload': {
                    'tool_name': 'workspace_write_file',
                    'arguments': {'path': 'README.md'},
                },
            },
            {
                'run_id': 'test-files',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:03:00Z',
                'payload': {
                    'tool_name': 'workspace_write_file',
                    'arguments': {'path': 'src/main.py'},
                },
            },
            {
                'run_id': 'test-files',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-files', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-files', tmpdir)
            assert summary.status == 'success'
            assert sorted(summary.changed_files) == sorted(['README.md', 'src/main.py'])

    def test_summary_extracts_cost(self):
        events = [
            {
                'run_id': 'test-cost',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-cost',
                'event_type': 'tool_call',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {'estimated_cost_cents': 250},
            },
            {
                'run_id': 'test-cost',
                'event_type': 'tool_call',
                'timestamp': '2026-06-01T10:02:00Z',
                'payload': {'estimated_cost_cents': 100},
            },
            {
                'run_id': 'test-cost',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
                'payload': {'cost_cents': 350},
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-cost', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-cost', tmpdir)
            assert summary.total_cost_cents == 700

    def test_summary_detects_rollback(self):
        events = [
            {
                'run_id': 'test-rollback',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-rollback',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-rollback', events)
            write_undo_journal(tmpdir, 'test-rollback')
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-rollback', tmpdir)
            assert summary.rollback_available is True

    def test_summary_rollback_shell_partial_true(self):
        events = [
            {
                'run_id': 'shell-partial',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'shell-partial',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {
                    'call_id': 'c1',
                    'tool_name': 'workspace_run_shell_mutate',
                    'arguments': {'command': 'echo hi >> f.txt'},
                },
            },
            {
                'run_id': 'shell-partial',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'shell-partial', events)
            write_undo_journal(tmpdir, 'shell-partial')
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'shell-partial', tmpdir)
            assert summary.rollback_available is True
            assert summary.rollback_shell_partial is True
            assert summary.to_dict()['rollback_shell_partial'] is True

    def test_summary_rollback_shell_partial_false_for_file_only(self):
        events = [
            {
                'run_id': 'file-only',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'file-only',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {
                    'call_id': 'c1',
                    'tool_name': 'workspace_write_file',
                    'arguments': {'path': 'f.txt'},
                },
            },
            {
                'run_id': 'file-only',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'file-only', events)
            write_undo_journal(tmpdir, 'file-only')
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'file-only', tmpdir)
            assert summary.rollback_available is True
            assert summary.rollback_shell_partial is False

    def test_summary_failure_status(self):
        events = [
            {
                'run_id': 'test-failure',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-failure',
                'event_type': 'run_failed',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {
                    'cost_cents': 50,
                    'category': 'budget_exceeded',
                },
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-failure', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-failure', tmpdir)
            assert summary.status == 'failure'
            assert summary.total_cost_cents == 50

    def test_summary_pending_approval_status(self):
        events = [
            {
                'run_id': 'test-pending',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-pending',
                'event_type': 'run_paused',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {'status': 'pending_approval'},
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-pending', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-pending', tmpdir)
            assert summary.status == 'pending_approval'

    def test_summary_commands_and_tests(self):
        events = [
            {
                'run_id': 'test-ct',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-ct',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {
                    'tool_name': 'workspace_run_shell_mutate',
                    'arguments': {'command': 'rm -rf /tmp/old'},
                },
            },
            {
                'run_id': 'test-ct',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:02:00Z',
                'payload': {
                    'tool_name': 'pytest',
                    'arguments': {},
                },
            },
            {
                'run_id': 'test-ct',
                'event_type': 'tool_call_completed',
                'timestamp': '2026-06-01T10:03:00Z',
                'payload': {
                    'tool_name': 'run_test_suite',
                    'arguments': {},
                },
            },
            {
                'run_id': 'test-ct',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-ct', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-ct', tmpdir)
            assert len(summary.commands_run) == 1
            assert summary.commands_run[0]['command'] == 'rm -rf /tmp/old'
            assert summary.tests_executed == 2

    def test_summary_approvals(self):
        events = [
            {
                'run_id': 'test-approvals',
                'event_type': 'run_started',
                'timestamp': '2026-06-01T10:00:00Z',
            },
            {
                'run_id': 'test-approvals',
                'event_type': 'tool_call_pending_approval',
                'timestamp': '2026-06-01T10:01:00Z',
                'payload': {
                    'call_id': 'call-1',
                    'tool_name': 'workspace_write_file',
                    'scope': 'file',
                },
            },
            {
                'run_id': 'test-approvals',
                'event_type': 'approval_granted',
                'timestamp': '2026-06-01T10:01:05Z',
                'payload': {
                    'call_id': 'call-1',
                    'tool_name': 'workspace_write_file',
                    'scope': 'file',
                },
            },
            {
                'run_id': 'test-approvals',
                'event_type': 'approval_denied',
                'timestamp': '2026-06-01T10:02:00Z',
                'payload': {
                    'call_id': 'call-2',
                    'tool_name': 'workspace_run_shell_mutate',
                    'scope': 'session',
                },
            },
            {
                'run_id': 'test-approvals',
                'event_type': 'run_completed',
                'timestamp': '2026-06-01T10:05:00Z',
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_run_events(tmpdir, 'test-approvals', events)
            store = RunStore(tmpdir)
            summary = build_evidence_summary(store, 'test-approvals', tmpdir)
            assert len(summary.approvals) == 2
            decisions = {a['call_id']: a['decision'] for a in summary.approvals}
            assert decisions['call-1'] == 'granted'
            assert decisions['call-2'] == 'denied'

    def test_summary_to_dict(self):
        summary = RunEvidenceSummary(
            run_id='test-dict',
            status='success',
            changed_files=['a.py', 'b.py'],
            commands_run=[{'tool_name': 'shell', 'command': 'ls'}],
            tests_executed=3,
            approvals=[{'call_id': 'c1', 'decision': 'granted'}],
            total_cost_cents=500,
            rollback_available=True,
            started_at='2026-01-01T00:00:00Z',
            finished_at='2026-01-01T00:01:00Z',
        )
        d = summary.to_dict()
        assert d['run_id'] == 'test-dict'
        assert d['status'] == 'success'
        assert d['changed_files'] == ['a.py', 'b.py']
        assert d['tests_executed'] == 3
        assert d['total_cost_cents'] == 500
        assert d['rollback_available'] is True


class TestSummarizeRunEvents:
    def test_empty_events(self):
        result = summarize_run_events([])
        assert result['status'] == 'unknown'
        assert result['changed_files'] == []
        assert result['tests_executed'] == 0
        assert result['total_cost_cents'] == 0
        assert result['started_at'] == ''

    def test_status_running(self):
        events = [{'event_type': 'run_started', 'timestamp': '2026-01-01T00:00:00Z'}]
        result = summarize_run_events(events)
        assert result['status'] == 'running'
        assert result['finished_at'] is None

    def test_status_cancelled(self):
        events = [
            {
                'run_id': 'r',
                'event_type': 'run_started',
                'timestamp': 'T1',
            },
            {
                'run_id': 'r',
                'event_type': 'run_cancelled',
                'timestamp': 'T2',
            },
        ]
        result = summarize_run_events(events)
        assert result['status'] == 'cancelled'

    def test_handles_non_dict_payload(self):
        events = [
            {
                'event_type': 'run_started',
                'timestamp': 'T1',
                'payload': ['not', 'a', 'dict'],
            },
            {
                'event_type': 'run_completed',
                'timestamp': 'T2',
                'payload': None,
            },
        ]
        result = summarize_run_events(events)
        assert result['status'] == 'success'

    def test_uses_created_at_fallback(self):
        events = [
            {
                'event_type': 'run_started',
                'created_at': 'fallback-ts',
            },
            {
                'event_type': 'run_completed',
                'created_at': 'fallback-end',
            },
        ]
        result = summarize_run_events(events)
        assert result['started_at'] == 'fallback-ts'
        assert result['finished_at'] == 'fallback-end'
