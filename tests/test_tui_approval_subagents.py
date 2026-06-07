"""Tests for teaagent.tui._approval_subagents."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.tui._approval_subagents import (
    _build_approval_tree,
    _render_approval_tree,
    format_subagent_approval_batch,
    resolve_parent_run_id,
    tui_approve_subagent_request,
    tui_deny_subagent_request,
)

# ── _build_approval_tree ────────────────────────────────────────────────


class TestBuildApprovalTree:
    """Pure function; no mocking needed."""

    def test_flat_roots_when_no_batch_index(self) -> None:
        """Items without batch_index are all top-level roots."""
        items = [
            {'request_id': 'aaa', 'tool_name': 'write'},
            {'request_id': 'bbb', 'tool_name': 'delete'},
        ]
        roots = _build_approval_tree(items)
        assert len(roots) == 2
        assert roots[0]['item']['request_id'] == 'aaa'
        assert roots[1]['item']['request_id'] == 'bbb'
        assert roots[0]['children'] == []
        assert roots[1]['children'] == []

    def test_nests_children_by_batch_index_depth(self) -> None:
        """Items are nested by increasing batch_index."""
        items = [
            {'request_id': 'aaa', 'tool_name': 'write', 'batch_index': 1},
            {'request_id': 'bbb', 'tool_name': 'delete', 'batch_index': 2},
            {'request_id': 'ccc', 'tool_name': 'patch', 'batch_index': 2},
        ]
        roots = _build_approval_tree(items)
        assert len(roots) == 1
        assert roots[0]['item']['request_id'] == 'aaa'
        children = roots[0]['children']
        assert len(children) == 2
        assert children[0]['item']['request_id'] == 'bbb'
        assert children[1]['item']['request_id'] == 'ccc'

    def test_single_root(self) -> None:
        """A single item yields one root node."""
        items = [
            {'request_id': 'aaa', 'tool_name': 'write', 'batch_index': 1},
        ]
        roots = _build_approval_tree(items)
        assert len(roots) == 1
        assert roots[0]['item']['request_id'] == 'aaa'
        assert roots[0]['children'] == []

    def test_non_int_batch_index_treated_as_depth_1(self) -> None:
        """batch_index that is not a positive int is treated as depth 1."""
        items = [
            {'request_id': 'aaa', 'batch_index': None},
            {'request_id': 'bbb', 'batch_index': 'foo'},
            {'request_id': 'ccc', 'batch_index': 0},
        ]
        roots = _build_approval_tree(items)
        assert len(roots) == 3

    def test_batch_index_negative_treated_as_depth_1(self) -> None:
        """Negative batch_index is not > 0, so treated as depth 1."""
        items = [
            {'request_id': 'aaa', 'batch_index': -1},
            {'request_id': 'bbb', 'batch_index': -5},
        ]
        roots = _build_approval_tree(items)
        assert len(roots) == 2


# ── _render_approval_tree ──────────────────────────────────────────────


class TestRenderApprovalTree:
    """Pure function; no mocking needed."""

    def test_renders_with_correct_unicode_connectors(self) -> None:
        """Single root uses └── (last item connector)."""
        nodes = [
            {
                'item': {
                    'request_id': 'abc12345',
                    'subagent_name': 'agent-a',
                    'tool_name': 'write_file',
                    'batch_index': 1,
                },
                'children': [],
            }
        ]
        lines: list[str] = []
        _render_approval_tree(nodes, lines)
        assert len(lines) == 1
        assert lines[0].startswith('└── ')
        assert '[abc12345]' in lines[0]
        assert 'agent-a' in lines[0]
        assert 'write_file' in lines[0]

    def test_multiple_roots_uses_correct_connectors(self) -> None:
        """Multiple roots: ├── for non-last, └── for last."""
        nodes = [
            {
                'item': {
                    'request_id': 'aaa',
                    'subagent_name': 'a1',
                    'tool_name': 't1',
                    'batch_index': 1,
                },
                'children': [],
            },
            {
                'item': {
                    'request_id': 'bbb',
                    'subagent_name': 'b1',
                    'tool_name': 't2',
                    'batch_index': 1,
                },
                'children': [],
            },
        ]
        lines: list[str] = []
        _render_approval_tree(nodes, lines)
        assert lines[0].startswith('├── ')
        assert lines[1].startswith('└── ')

    def test_nested_children_proper_prefixes(self) -> None:
        """Children are indented with │   for non-last siblings."""
        nodes = [
            {
                'item': {
                    'request_id': 'aaa',
                    'subagent_name': 'parent',
                    'tool_name': 'p',
                    'batch_index': 1,
                },
                'children': [
                    {
                        'item': {
                            'request_id': 'bbb',
                            'subagent_name': 'child1',
                            'tool_name': 'c1',
                            'batch_index': 2,
                        },
                        'children': [],
                    },
                    {
                        'item': {
                            'request_id': 'ccc',
                            'subagent_name': 'child2',
                            'tool_name': 'c2',
                            'batch_index': 2,
                        },
                        'children': [],
                    },
                ],
            }
        ]
        lines: list[str] = []
        _render_approval_tree(nodes, lines)
        # Root uses └──  (single root, last)
        assert lines[0].startswith('└── ')
        # First child uses ├──  and is indented with │
        assert lines[1].startswith('    ├── ')
        # Second child uses └──  and is indented with │
        assert lines[2].startswith('    └── ')

    def test_missing_keys_renders_unknown(self) -> None:
        """Items missing request_id/subagent_name/tool_name show 'unknown'."""
        nodes = [
            {
                'item': {},
                'children': [],
            }
        ]
        lines: list[str] = []
        _render_approval_tree(nodes, lines)
        assert 'unknown' in lines[0]


# ── format_subagent_approval_batch ──────────────────────────────────────


MOCK_PENDING_ITEM: dict = {
    'request_id': 'req-001-abcdef',
    'subagent_id': 'sa-1',
    'parent_run_id': 'run-1',
    'subagent_name': 'explorer',
    'tool_name': 'write_file',
    'tool_arguments': {},
    'permission_mode': 'workspace-write',
    'isolation': 'sandbox',
    'batch_index': 1,
    'status': 'pending',
}


class TestFormatSubagentApprovalBatch:
    """Uses mocks for snapshot_pending_subagent_requests / list_active_parent_run_ids."""

    def test_empty_summary_when_no_pending(self) -> None:
        """Returns empty note when there are no pending requests."""
        with (
            patch(
                'teaagent.tui._approval_subagents.snapshot_pending_subagent_requests',
                return_value=[],
            ),
            patch(
                'teaagent.tui._approval_subagents.list_active_parent_run_ids',
                return_value=[],
            ),
        ):
            summary, payload = format_subagent_approval_batch(
                workspace_root=Path('/fake/root')
            )
        assert '(no pending destructive tool requests)' in summary
        assert payload['count'] == 0
        assert payload['pending'] == []

    def test_includes_parent_run_id_in_payload_when_provided(self) -> None:
        """When parent_run_id is explicit, it appears in the payload."""
        with (
            patch(
                'teaagent.tui._approval_subagents.snapshot_pending_subagent_requests',
                return_value=[MOCK_PENDING_ITEM],
            ),
        ):
            summary, payload = format_subagent_approval_batch(parent_run_id='run-1')
        assert payload['parent_run_id'] == 'run-1'
        assert 'run-1' in payload['parent_run_ids']
        assert 'parent_run_id: run-1' in summary

    def test_shows_active_parents_when_no_explicit(self) -> None:
        """Without explicit parent_run_id, shows active_parents in summary."""
        with (
            patch(
                'teaagent.tui._approval_subagents.snapshot_pending_subagent_requests',
                return_value=[],
            ),
            patch(
                'teaagent.tui._approval_subagents.list_active_parent_run_ids',
                return_value=['run-a', 'run-b'],
            ),
        ):
            summary, payload = format_subagent_approval_batch()
        assert 'active_parents: run-a, run-b' in summary
        assert payload['parent_run_ids'] == ['run-a', 'run-b']

    def test_shows_flat_items_when_no_batch_index(self) -> None:
        """Items without batch_index use bullet format (•)."""
        item_no_batch = dict(MOCK_PENDING_ITEM)
        item_no_batch.pop('batch_index', None)
        with (
            patch(
                'teaagent.tui._approval_subagents.snapshot_pending_subagent_requests',
                return_value=[item_no_batch],
            ),
        ):
            summary, payload = format_subagent_approval_batch(parent_run_id='run-1')
        assert '•' in summary
        assert payload['count'] == 1

    def test_shows_tree_when_batch_index_present(self) -> None:
        """Items with batch_index use tree rendering."""
        with (
            patch(
                'teaagent.tui._approval_subagents.snapshot_pending_subagent_requests',
                return_value=[MOCK_PENDING_ITEM],
            ),
        ):
            summary, payload = format_subagent_approval_batch(parent_run_id='run-1')
        assert '└── ' in summary
        assert payload['count'] == 1

    def test_payload_has_usage_hints(self) -> None:
        """Summary includes approve/deny usage hints when there are pending items."""
        with (
            patch(
                'teaagent.tui._approval_subagents.snapshot_pending_subagent_requests',
                return_value=[MOCK_PENDING_ITEM],
            ),
        ):
            summary, payload = format_subagent_approval_batch(parent_run_id='run-1')
        assert 'approve one:' in summary
        assert 'deny one:' in summary
        assert 'approve all:' in summary
        assert 'deny all:' in summary


# ── resolve_parent_run_id ──────────────────────────────────────────────


class TestResolveParentRunId:
    """Uses mocks for list_active_parent_run_ids."""

    def test_returns_explicit_when_provided(self) -> None:
        """Explicit argument always wins."""
        result = resolve_parent_run_id('explicit-run', fallback='fallback-run')
        assert result == 'explicit-run'

    def test_returns_fallback_when_explicit_is_none(self) -> None:
        """Fallback returned when explicit is None."""
        result = resolve_parent_run_id(None, fallback='fallback-run')
        assert result == 'fallback-run'

    def test_returns_fallback_when_explicit_empty(self) -> None:
        """Empty string explicit is falsy, so fallback returned."""
        result = resolve_parent_run_id('', fallback='fallback-run')
        assert result == 'fallback-run'

    def test_returns_active_when_both_none_and_one_active(self) -> None:
        """Single active parent run ID is returned when no explicit or fallback."""
        with patch(
            'teaagent.tui._approval_subagents.list_active_parent_run_ids',
            return_value=['only-active'],
        ):
            result = resolve_parent_run_id(None, fallback=None)
        assert result == 'only-active'

    def test_returns_none_when_both_none_and_multiple_active(self) -> None:
        """Returns None when ambiguity — multiple active parents."""
        with patch(
            'teaagent.tui._approval_subagents.list_active_parent_run_ids',
            return_value=['run-a', 'run-b'],
        ):
            result = resolve_parent_run_id(None, fallback=None)
        assert result is None

    def test_returns_none_when_both_none_and_no_active(self) -> None:
        """Returns None when both explicit and fallback are None and no active parents."""
        with patch(
            'teaagent.tui._approval_subagents.list_active_parent_run_ids',
            return_value=[],
        ):
            result = resolve_parent_run_id(None, fallback=None)
        assert result is None


# ── tui_approve_subagent_request ────────────────────────────────────────


def _mock_queue(approve_sync_return: bool = True) -> MagicMock:
    q = MagicMock()
    q.approve_request_sync.return_value = approve_sync_return
    return q


class TestTuiApproveSubagentRequest:
    """Uses mocks for try_get_approval_queue and approve_request_cross_process."""

    def test_success_via_queue_sync(self) -> None:
        """Returns (True, msg) when queue.approve_request_sync succeeds."""
        queue = _mock_queue(approve_sync_return=True)
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.approve_request_cross_process',
            ) as mock_cross,
        ):
            ok, msg = tui_approve_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is True
        assert 'approved' in msg
        queue.approve_request_sync.assert_called_once_with('req-1')
        mock_cross.assert_not_called()

    def test_fallback_to_cross_process_when_queue_fails(self) -> None:
        """Calls approve_request_cross_process when queue.approve_request_sync fails."""
        queue = _mock_queue(approve_sync_return=False)
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.approve_request_cross_process',
                return_value=True,
            ) as mock_cross,
        ):
            ok, msg = tui_approve_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is True
        assert 'approved' in msg
        mock_cross.assert_called_once()

    def test_fallback_to_cross_process_when_queue_none(self) -> None:
        """Calls approve_request_cross_process when try_get_approval_queue returns None."""
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=None,
            ),
            patch(
                'teaagent.tui._approval_subagents.approve_request_cross_process',
                return_value=True,
            ) as mock_cross,
        ):
            ok, msg = tui_approve_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is True
        assert 'approved' in msg
        mock_cross.assert_called_once()

    def test_returns_false_when_request_not_found(self) -> None:
        """Returns (False, msg) when both queue sync and cross-process fail."""
        queue = _mock_queue(approve_sync_return=False)
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.approve_request_cross_process',
                return_value=False,
            ),
        ):
            ok, msg = tui_approve_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is False
        assert 'not found' in msg.lower()

    def test_returns_false_when_queue_none_and_cross_fails(self) -> None:
        """Returns (False, msg) when no queue and cross-process also fails."""
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=None,
            ),
            patch(
                'teaagent.tui._approval_subagents.approve_request_cross_process',
                return_value=False,
            ),
        ):
            ok, msg = tui_approve_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is False
        assert 'not found' in msg.lower()


# ── tui_deny_subagent_request ───────────────────────────────────────────


class TestTuiDenySubagentRequest:
    """Uses mocks for try_get_approval_queue and deny_request_cross_process."""

    def test_success_via_queue_sync(self) -> None:
        """Returns (True, msg) when queue.deny_request_sync succeeds."""
        queue = MagicMock()
        queue.deny_request_sync.return_value = True
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.deny_request_cross_process',
            ) as mock_cross,
        ):
            ok, msg = tui_deny_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is True
        assert 'denied' in msg
        queue.deny_request_sync.assert_called_once_with(
            'req-1', reason='Denied by operator'
        )
        mock_cross.assert_not_called()

    def test_fallback_to_cross_process_when_queue_fails(self) -> None:
        """Calls deny_request_cross_process when queue.deny_request_sync fails."""
        queue = MagicMock()
        queue.deny_request_sync.return_value = False
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.deny_request_cross_process',
                return_value=True,
            ) as mock_cross,
        ):
            ok, msg = tui_deny_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is True
        assert 'denied' in msg
        mock_cross.assert_called_once()

    def test_returns_false_when_request_not_found(self) -> None:
        """Returns (False, msg) when both queue and cross-process fail."""
        queue = MagicMock()
        queue.deny_request_sync.return_value = False
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.deny_request_cross_process',
                return_value=False,
            ),
        ):
            ok, msg = tui_deny_subagent_request(
                'req-1', 'run-1', workspace_root=Path('/fake')
            )
        assert ok is False
        assert 'not found' in msg.lower()

    def test_custom_reason_passed_through(self) -> None:
        """Custom reason string is passed to deny_request_sync."""
        queue = MagicMock()
        queue.deny_request_sync.return_value = True
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.deny_request_cross_process',
            ),
        ):
            ok, msg = tui_deny_subagent_request(
                'req-1',
                'run-1',
                workspace_root=Path('/fake'),
                reason='Security violation',
            )
        assert ok is True
        queue.deny_request_sync.assert_called_once_with(
            'req-1', reason='Security violation'
        )

    def test_deny_with_custom_reason_via_cross_process(self) -> None:
        """Custom reason is passed to deny_request_cross_process when queue fails."""
        queue = MagicMock()
        queue.deny_request_sync.return_value = False
        with (
            patch(
                'teaagent.tui._approval_subagents.try_get_approval_queue',
                return_value=queue,
            ),
            patch(
                'teaagent.tui._approval_subagents.deny_request_cross_process',
                return_value=True,
            ) as mock_cross,
        ):
            ok, msg = tui_deny_subagent_request(
                'req-1',
                'run-1',
                workspace_root=Path('/fake'),
                reason='User veto',
            )
        assert ok is True
        mock_cross.assert_called_once()
        call_kwargs = mock_cross.call_args[1]
        assert call_kwargs.get('reason') == 'User veto'
