"""Unit tests for shared resume preparation."""

from __future__ import annotations

import tempfile

import pytest

from teaagent.integration.resume_preparation import (
    ResumePreparationError,
    prepare_run_resume,
)
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger


def test_prepare_run_resume_compacts_large_observation_history() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_id = 'compact-run'
        store = RunStore(tmp)
        audit = AuditLogger(path=store.run_path(run_id))
        audit.record('run_started', run_id, task='long task')
        for i in range(45):
            audit.record(
                'tool_call_completed',
                run_id,
                call_id=f'c{i}',
                tool_name='grep',
                result={'i': i},
            )

        prepared = prepare_run_resume(tmp, run_id, auto_compact=True)
        assert len(prepared.initial_observations) == 20
        assert prepared.initial_context_extra is not None
        assert prepared.initial_context_extra['resume_compaction']['truncated'] is True


def test_prepare_run_resume_missing_run_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp, pytest.raises(ResumePreparationError):
        prepare_run_resume(tmp, 'missing-run')
