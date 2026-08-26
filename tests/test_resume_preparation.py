"""Unit tests for shared resume preparation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from teaagent.ergonomics._approval_grants import _compute_argument_digest
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.integration.resume_preparation import (
    ResumePreparationError,
    prepare_run_resume,
)
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger

_DEFAULT_ARGS = {'path': 'a.txt', 'content': 'hi'}


def _seed_pending(
    tmp: str,
    run_id: str = 'pending-run',
    *,
    with_digest: bool = True,
    args: dict[str, Any] | None = None,
) -> str:
    """Seed a run with one pending tool-call approval. Returns the call_id."""
    args_payload = args if args is not None else dict(_DEFAULT_ARGS)
    store = RunStore(tmp)
    audit = AuditLogger(path=store.run_path(run_id))
    audit.record('run_started', run_id, task='finish write', permission_mode='prompt')
    extra: dict[str, Any] = {}
    if with_digest:
        extra = {
            'argument_digest': _compute_argument_digest(args_payload),
            'argument_digest_version': 'v1',
        }
    audit.record(
        'tool_call_pending_approval',
        run_id,
        call_id='write-1',
        tool_name='workspace_write_file',
        arguments=args_payload,
        **extra,
    )
    return 'write-1'


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


# --- SURF-010 P0 permission-boundary tests (governance/test-matrices/SURF-010.md) ---


def test_legacy_record_without_digest_warns_and_does_not_auto_grant() -> None:
    """Row 4 (P0): a pending record with no argument_digest must warn, never grant."""
    with tempfile.TemporaryDirectory() as tmp:
        call_id = _seed_pending(tmp, 'legacy-run', with_digest=False)

        prepared = prepare_run_resume(tmp, 'legacy-run')

        assert prepared.auto_approved_call_id is None
        assert prepared.pending_warning is not None
        assert call_id in prepared.pending_warning
        # Negative post-state: nothing was granted into the approval store.
        store = ApprovalPresetStore(tmp)
        assert store.list_scoped_approvals_for_run('legacy-run') == []


def test_pre_approved_call_id_is_skipped_not_re_granted() -> None:
    """Row 5 (P0): a call already in approve_call_ids must not auto-grant or warn."""
    with tempfile.TemporaryDirectory() as tmp:
        call_id = _seed_pending(tmp, 'preapproved-run')

        prepared = prepare_run_resume(
            tmp, 'preapproved-run', approve_call_ids=frozenset({call_id})
        )

        assert prepared.auto_approved_call_id is None
        assert prepared.pending_warning is None
        store = ApprovalPresetStore(tmp)
        assert store.list_scoped_approvals_for_run('preapproved-run') == []


def test_auto_grant_is_bound_to_exact_digest() -> None:
    """Row 3 (P0): the grant binds the exact digest; a tampered digest matches nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        call_id = _seed_pending(tmp, 'bound-run')
        good_digest = _compute_argument_digest(_DEFAULT_ARGS)

        prepared = prepare_run_resume(tmp, 'bound-run')

        assert prepared.auto_approved_call_id == call_id
        store = ApprovalPresetStore(tmp)
        # Positive post-state: a grant exists for the exact recorded digest.
        assert (
            store.check_scoped_approval_digest(
                run_id='bound-run',
                call_id=call_id,
                tool_name='workspace_write_file',
                argument_digest=good_digest,
            )
            is not None
        )
        # Negative post-state: a tampered (different) digest finds no grant, so a
        # tampered argument set could not consume this approval.
        assert (
            store.check_scoped_approval_digest(
                run_id='bound-run',
                call_id=call_id,
                tool_name='workspace_write_file',
                argument_digest='deadbeefdeadbeef',
            )
            is None
        )
        # Exactly one approval was created (no over-granting).
        assert len(store.list_scoped_approvals_for_run('bound-run')) == 1


def test_auto_grant_is_idempotent_when_already_scoped() -> None:
    """Pre-existing scoped approval must not be duplicated but is still reported."""
    with tempfile.TemporaryDirectory() as tmp:
        call_id = _seed_pending(tmp, 'idem-run')
        digest = _compute_argument_digest(_DEFAULT_ARGS)
        store = ApprovalPresetStore(tmp)
        store.add_scoped_approval(
            run_id='idem-run',
            call_id=call_id,
            tool_name='workspace_write_file',
            arguments=dict(_DEFAULT_ARGS),
            argument_digest=digest,
        )

        prepared = prepare_run_resume(tmp, 'idem-run')

        assert prepared.auto_approved_call_id == call_id
        assert len(store.list_scoped_approvals_for_run('idem-run')) == 1


def test_fresh_restart_skips_pending_auto_grant() -> None:
    """fresh_restart=True must skip observations and never auto-grant."""
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending(tmp, 'fresh-run')

        prepared = prepare_run_resume(tmp, 'fresh-run', fresh_restart=True)

        assert prepared.auto_approved_call_id is None
        assert prepared.pending_warning is None
        assert prepared.initial_observations == []
        store = ApprovalPresetStore(tmp)
        assert store.list_scoped_approvals_for_run('fresh-run') == []


def test_auto_approve_pending_false_warns_without_granting() -> None:
    """Row 11 (P1): auto_approve_pending=False (TUI default) must warn, never grant.

    The branch was added when CLI/TUI resume diverged; this guards it at the
    prepare layer so the surface-independent contract is enforced directly.
    """
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending(tmp, 'noauto-run')

        prepared = prepare_run_resume(tmp, 'noauto-run', auto_approve_pending=False)

        assert prepared.auto_approved_call_id is None
        assert prepared.pending_warning is not None
        assert 'noauto-run' in prepared.pending_warning
        store = ApprovalPresetStore(tmp)
        assert store.list_scoped_approvals_for_run('noauto-run') == []


def test_unmatched_effect_warning_blocks_auto_grant() -> None:
    """EFX-001: checkpointed pending_effect (OUTCOME_UNKNOWN) must suppress
    auto-grant for EVERY auto_approve_pending value — auto-granting a scoped
    approval while a non-idempotent effect is unconfirmed is exactly the
    blind-redispatch hazard. Kills the warning-guard mutants (True case) and
    the knob-inversion mutant (False case).
    """
    from teaagent.checkpoint import SQLiteCheckpointStore
    from teaagent.policy import compute_scoped_payload_digest

    for auto_approve in (True, False):
        with tempfile.TemporaryDirectory() as tmp:
            run_id = 'unknown-effect-run'
            _seed_pending(tmp, run_id)

            ckpt_path = Path(tmp) / 'ckpt.sqlite'
            digest = compute_scoped_payload_digest(
                'workspace_write_file', dict(_DEFAULT_ARGS)
            )
            SQLiteCheckpointStore(ckpt_path).save(
                run_id,
                {
                    'task': 'finish write',
                    'observations': [],
                    'pending_effect': {
                        'call_id': 'write-1',
                        'tool_name': 'workspace_write_file',
                        'payload_digest': digest,
                        'idempotent': False,
                        'retry_safe': False,
                        'outcome': 'OUTCOME_UNKNOWN',
                    },
                },
            )

            prepared = prepare_run_resume(
                tmp,
                run_id,
                auto_approve_pending=auto_approve,
                checkpoint_path=ckpt_path,
            )

            assert prepared.auto_approved_call_id is None, auto_approve
            assert prepared.pending_warning is not None
            assert prepared.pending_warning.startswith('Unmatched mutating tool start')
            # Negative post-state: no scoped approval may exist for the run.
            store = ApprovalPresetStore(tmp)
            assert store.list_scoped_approvals_for_run(run_id) == []
