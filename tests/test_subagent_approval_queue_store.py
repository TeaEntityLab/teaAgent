from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueuePruneReport,
    ApprovalQueueStore,
    QueueDiskSnapshot,
    default_hmac_secret,
    pending_requests_from_snapshot,
    request_from_dict,
)


def _make_req(**overrides: object) -> SubagentApprovalRequest:
    fields = {
        'request_id': 'r1',
        'subagent_id': 's1',
        'parent_run_id': 'parent-1',
        'subagent_name': 'test',
        'tool_name': 'bash',
        'tool_arguments': {'cmd': 'ls'},
        'permission_mode': 'destructive',
        'isolation': 'shared',
    }
    fields.update(overrides)
    return SubagentApprovalRequest(**fields)  # type: ignore[arg-type]


class TestQueueDiskSnapshot:
    def test_default_construction(self) -> None:
        snap = QueueDiskSnapshot('run-1', {}, {})
        assert snap.parent_run_id == 'run-1'
        assert snap.requests == {}
        assert snap.batches == {}


class TestApprovalQueuePruneReport:
    def test_removed_count(self) -> None:
        report = ApprovalQueuePruneReport(
            removed_parent_run_ids=['a', 'b'],
            skipped_pending=['c'],
            skipped_recent=['d'],
        )
        assert report.removed_count == 2

    def test_empty_report(self) -> None:
        report = ApprovalQueuePruneReport()
        assert report.removed_count == 0


class TestApprovalQueueStore:
    def test_queue_path_uses_safe_id(self) -> None:
        store = ApprovalQueueStore(Path('/tmp'))
        path = store.queue_path('run/with/slashes')
        assert 'run_with_slashes' in path.name
        assert path.suffix == '.json'

    def test_list_parent_run_ids_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            assert store.list_parent_run_ids() == []

    def test_exists_returns_false_for_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            assert not store.exists('nonexistent')

    def test_save_and_load_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            req = _make_req(
                request_id='r1',
                subagent_name='test-agent',
                tool_name='bash',
                tool_arguments={'cmd': 'ls'},
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='parent-1',
                created_at='2025-01-01T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save('parent-1', {'r1': req}, {'b1': batch})
            assert store.exists('parent-1')
            snap = store.load('parent-1')
            assert snap.parent_run_id == 'parent-1'
            assert 'r1' in snap.requests
            assert snap.requests['r1']['tool_name'] == 'bash'
            assert 'b1' in snap.batches

    def test_load_returns_empty_for_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            snap = store.load('nonexistent')
            assert snap.requests == {}
            assert snap.batches == {}

    def test_hmac_integrity_check(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp), hmac_secret='test-secret')
            req = _make_req(
                request_id='r1',
                subagent_id='s1',
                parent_run_id='parent-1',
                subagent_name='test',
                tool_name='read',
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='parent-1',
                created_at='2025-01-01T00:00:00',
            )
            store.save('parent-1', {'r1': req}, {'b1': batch})
            snap = store.load('parent-1')
            assert 'r1' in snap.requests

    def test_hmac_rejects_tampered_data(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp), hmac_secret='test-secret')
            req = _make_req(
                request_id='r1',
                subagent_id='s1',
                parent_run_id='parent-1',
                subagent_name='test',
                tool_name='read',
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='parent-1',
                created_at='2025-01-01T00:00:00',
            )
            store.save('parent-1', {'r1': req}, {'b1': batch})

            path = store.queue_path('parent-1')
            data = json.loads(path.read_text(encoding='utf-8'))
            data['requests']['r1']['tool_name'] = 'rm'
            path.write_text(json.dumps(data), encoding='utf-8')

            snap = store.load('parent-1')
            assert snap.requests == {}

    def test_update_request_status(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            req = _make_req(
                request_id='r1',
                subagent_id='s1',
                parent_run_id='parent-1',
                subagent_name='test',
                tool_name='bash',
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='parent-1',
                created_at='2025-01-01T00:00:00',
            )
            store.save('parent-1', {'r1': req}, {'b1': batch})

            result = store.update_request_status(
                'parent-1',
                'r1',
                ApprovalRequestStatus.APPROVED,
                approved_by='test-user',
            )
            assert result is True

            snap = store.load('parent-1')
            assert snap.requests['r1']['status'] == ApprovalRequestStatus.APPROVED.value
            assert snap.requests['r1']['approved_by'] == 'test-user'

    def test_update_request_status_returns_false_for_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            req = _make_req(request_id='existing')
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='parent-1',
                created_at='2025-01-01T00:00:00',
            )
            store.save('parent-1', {'existing': req}, {'b1': batch})
            result = store.update_request_status(
                'parent-1', 'nonexistent', ApprovalRequestStatus.APPROVED
            )
            assert result is False

    def test_prune_stale_removes_old_files(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            req = _make_req(
                request_id='r1',
                subagent_id='s1',
                parent_run_id='old-run',
                tool_name='read',
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='old-run',
                created_at='2025-01-01T00:00:00',
            )
            store.save('old-run', {'r1': req}, {'b1': batch})
            store.update_request_status(
                'old-run', 'r1', ApprovalRequestStatus.APPROVED, approved_by='test'
            )

            path = store.queue_path('old-run')
            old_mtime = 100000.0
            os.utime(path, (old_mtime, old_mtime))

            report = store.prune_stale(max_age_seconds=100, now=old_mtime + 200)
            assert 'old-run' in report.removed_parent_run_ids
            assert not store.exists('old-run')

    def test_prune_stale_skips_recent_files(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            req = _make_req(
                request_id='r1',
                subagent_id='s1',
                parent_run_id='recent',
                subagent_name='test',
                tool_name='read',
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='recent',
                created_at='2025-01-01T00:00:00',
            )
            store.save('recent', {'r1': req}, {'b1': batch})

            report = store.prune_stale(max_age_seconds=3600, now=10.0)
            assert 'recent' in report.skipped_recent

    def test_prune_stale_skips_pending(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            req = _make_req(
                request_id='r1',
                subagent_id='s1',
                parent_run_id='pending-run',
                subagent_name='test',
                tool_name='read',
            )
            batch = ApprovalBatch(
                batch_id='b1',
                parent_run_id='pending-run',
                created_at='2025-01-01T00:00:00',
            )
            store.save('pending-run', {'r1': req}, {'b1': batch})

            report = store.prune_stale(max_age_seconds=0, now=9999999999.0)
            assert 'pending-run' in report.skipped_pending

    def test_list_parent_run_ids_after_save(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ApprovalQueueStore(Path(tmp))
            store.save('run-1', {}, {})
            store.save('run-2', {}, {})
            ids = store.list_parent_run_ids()
            assert 'run-1' in ids
            assert 'run-2' in ids


class TestDefaultHmacSecret:
    def test_returns_none_when_unset(self) -> None:
        if 'TEAAGENT_APPROVAL_HMAC_KEY' in os.environ:
            del os.environ['TEAAGENT_APPROVAL_HMAC_KEY']
        assert default_hmac_secret() is None

    def test_returns_value_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('TEAAGENT_APPROVAL_HMAC_KEY', 'my-secret')
        assert default_hmac_secret() == 'my-secret'

    def test_returns_none_for_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('TEAAGENT_APPROVAL_HMAC_KEY', '')
        assert default_hmac_secret() is None


class TestRequestFromDict:
    def test_minimal_dict(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
        }
        req = request_from_dict(data)
        assert req.request_id == 'r1'
        assert req.status == ApprovalRequestStatus.PENDING
        assert req.timeout_seconds == 180

    def test_full_dict(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test',
            'tool_name': 'write',
            'tool_arguments': {'path': '/tmp/x'},
            'permission_mode': 'destructive',
            'isolation': 'worktree',
            'batch_index': 0,
            'status': ApprovalRequestStatus.APPROVED.value,
            'approved_at': '2025-01-01T00:00:00',
            'approved_by': 'user',
            'timeout_seconds': 60,
        }
        req = request_from_dict(data)
        assert req.status == ApprovalRequestStatus.APPROVED
        assert req.timeout_seconds == 60
        assert req.tool_arguments == {'path': '/tmp/x'}

    def test_missing_required_field_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            # Missing tool_name
        }
        with pytest.raises(ValueError, match='Missing required field: tool_name'):
            request_from_dict(data)

    def test_empty_required_field_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': '',  # Empty string
        }
        with pytest.raises(
            ValueError, match="Required field 'tool_name' cannot be empty"
        ):
            request_from_dict(data)

    def test_none_required_field_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': None,  # None value
        }
        with pytest.raises(
            ValueError, match="Required field 'tool_name' cannot be empty"
        ):
            request_from_dict(data)

    def test_invalid_status_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'status': 'invalid_status',
        }
        with pytest.raises(ValueError, match="Invalid status 'invalid_status'"):
            request_from_dict(data)

    def test_invalid_tool_arguments_type_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'tool_arguments': 'not_a_dict',  # Should be dict
        }
        with pytest.raises(ValueError, match='tool_arguments must be a dict'):
            request_from_dict(data)

    def test_invalid_timeout_seconds_type_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'timeout_seconds': 'not_a_number',
        }
        with pytest.raises(ValueError, match='Invalid timeout_seconds'):
            request_from_dict(data)

    def test_negative_timeout_seconds_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'timeout_seconds': -10,
        }
        with pytest.raises(ValueError, match='must be positive'):
            request_from_dict(data)

    def test_zero_timeout_seconds_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'timeout_seconds': 0,
        }
        with pytest.raises(ValueError, match='timeout_seconds must be positive'):
            request_from_dict(data)

    def test_invalid_batch_index_type_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'batch_index': 'not_a_number',
        }
        with pytest.raises(ValueError, match='Invalid batch_index'):
            request_from_dict(data)

    def test_negative_batch_index_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'batch_index': -1,
        }
        with pytest.raises(ValueError, match='must be non-negative'):
            request_from_dict(data)

    def test_invalid_timestamp_type_raises_error(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'created_at': 123456,  # Should be string
        }
        with pytest.raises(
            ValueError, match="Field 'created_at' must be a string or None"
        ):
            request_from_dict(data)

    def test_valid_enum_status_values(self) -> None:
        """Test all valid enum status values are accepted."""
        valid_statuses = [
            ApprovalRequestStatus.PENDING.value,
            ApprovalRequestStatus.APPROVED.value,
            ApprovalRequestStatus.DENIED.value,
            ApprovalRequestStatus.TIMEOUT.value,
            ApprovalRequestStatus.CANCELLED.value,
        ]

        for status_value in valid_statuses:
            data = {
                'request_id': 'r1',
                'subagent_id': 's1',
                'parent_run_id': 'p1',
                'subagent_name': 'test-agent',
                'tool_name': 'bash',
                'status': status_value,
            }
            req = request_from_dict(data)
            assert req.status.value == status_value

    def test_none_tool_arguments_defaults_to_empty_dict(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'tool_arguments': None,
        }
        req = request_from_dict(data)
        assert req.tool_arguments == {}

    def test_string_timeout_converts_to_int(self) -> None:
        data = {
            'request_id': 'r1',
            'subagent_id': 's1',
            'parent_run_id': 'p1',
            'subagent_name': 'test-agent',
            'tool_name': 'bash',
            'timeout_seconds': '300',
        }
        req = request_from_dict(data)
        assert req.timeout_seconds == 300


class TestPendingRequestsFromSnapshot:
    def test_filters_pending(self) -> None:
        snap = QueueDiskSnapshot(
            parent_run_id='p1',
            requests={
                'r1': {
                    'request_id': 'r1',
                    'subagent_id': 's1',
                    'parent_run_id': 'p1',
                    'subagent_name': 'test',
                    'tool_name': 'read',
                    'status': ApprovalRequestStatus.PENDING.value,
                },
                'r2': {
                    'request_id': 'r2',
                    'subagent_id': 's1',
                    'parent_run_id': 'p1',
                    'subagent_name': 'test',
                    'tool_name': 'write',
                    'status': ApprovalRequestStatus.APPROVED.value,
                },
            },
            batches={},
        )
        pending = pending_requests_from_snapshot(snap)
        assert len(pending) == 1
        assert pending[0].request_id == 'r1'

    def test_returns_empty_when_none_pending(self) -> None:
        snap = QueueDiskSnapshot('p1', {}, {})
        assert pending_requests_from_snapshot(snap) == []
