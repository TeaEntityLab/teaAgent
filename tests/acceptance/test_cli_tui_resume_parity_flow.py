"""SURF-010: CLI and TUI resume must prepare identical trust inputs."""

from __future__ import annotations

import tempfile

from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.integration.resume_preparation import prepare_run_resume
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger


def _seed_pending_run(root: str, run_id: str = 'resume-parity') -> None:
    from teaagent.ergonomics._approval_grants import _compute_argument_digest

    store = RunStore(root)
    audit = AuditLogger(path=store.run_path(run_id))
    audit.record('run_started', run_id, task='finish write', permission_mode='prompt')
    args_payload = {'path': 'a.txt', 'content': 'hi'}
    digest = _compute_argument_digest(args_payload)
    audit.record(
        'tool_call_pending_approval',
        run_id,
        call_id='write-1',
        tool_name='workspace_write_file',
        arguments=args_payload,
        argument_digest=digest,
        argument_digest_version='v1',
    )


def test_prepare_run_resume_auto_grants_pending_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending_run(tmp)
        prepared = prepare_run_resume(tmp, 'resume-parity')
        assert prepared.original_task == 'finish write'
        assert prepared.auto_approved_call_id == 'write-1'
        assert prepared.pending_warning is None

        store = ApprovalPresetStore(tmp)
        from teaagent.ergonomics._approval_grants import _compute_argument_digest

        digest = _compute_argument_digest({'path': 'a.txt', 'content': 'hi'})
        assert store.check_scoped_approval_digest(
            run_id='resume-parity',
            call_id='write-1',
            tool_name='workspace_write_file',
            argument_digest=digest,
        )


def test_cli_and_tui_resume_use_same_preparation_contract() -> None:
    """Both surfaces call prepare_run_resume with equivalent defaults."""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending_run(tmp, 'shared-run')
        cli_prepared = prepare_run_resume(
            tmp,
            'shared-run',
            approve_call_ids=frozenset(),
            auto_compact=True,
        )
        tui_prepared = prepare_run_resume(
            tmp,
            'shared-run',
            approve_call_ids=frozenset(),
            auto_compact=True,
        )
        assert cli_prepared.to_dict() == tui_prepared.to_dict()
