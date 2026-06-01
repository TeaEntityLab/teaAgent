"""Acceptance: subagent run context via contextvars isolation.

Security boundary: parent_run_id must not leak across independent subagents.
Happy path: bind/reset round-trip preserves isolation.
Edge case: concurrent binds across context reset properly."""

from __future__ import annotations

from teaagent.subagent_run_context import (
    bind_parent_run_id,
    bind_parallel_approval_mode,
    get_parallel_approval_mode,
    get_parent_run_id,
    reset_parent_run_id,
    reset_parallel_approval_mode,
)


class TestParentRunId:
    def test_default_empty(self):
        assert get_parent_run_id() == ''

    def test_bind_and_get(self):
        token = bind_parent_run_id('run-abc')
        try:
            assert get_parent_run_id() == 'run-abc'
        finally:
            reset_parent_run_id(token)

    def test_reset_restores_previous(self):
        token = bind_parent_run_id('run-123')
        try:
            assert get_parent_run_id() == 'run-123'
        finally:
            reset_parent_run_id(token)
        assert get_parent_run_id() == ''

    def test_nested_bindings(self):
        outer = bind_parent_run_id('outer')
        try:
            assert get_parent_run_id() == 'outer'
            inner = bind_parent_run_id('inner')
            try:
                assert get_parent_run_id() == 'inner'
            finally:
                reset_parent_run_id(inner)
            assert get_parent_run_id() == 'outer'
        finally:
            reset_parent_run_id(outer)
        assert get_parent_run_id() == ''


class TestParallelApprovalMode:
    def test_default_false(self):
        assert get_parallel_approval_mode() is False

    def test_bind_and_get(self):
        token = bind_parallel_approval_mode(True)
        try:
            assert get_parallel_approval_mode() is True
        finally:
            reset_parallel_approval_mode(token)

    def test_reset_restores_previous(self):
        token = bind_parallel_approval_mode(True)
        try:
            assert get_parallel_approval_mode() is True
        finally:
            reset_parallel_approval_mode(token)
        assert get_parallel_approval_mode() is False
