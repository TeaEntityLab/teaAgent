"""Shared run resume preparation for CLI, TUI, and attach flows (SURF-010)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.run_store import RunStore


class ResumePreparationError(Exception):
    """Raised when a run cannot be prepared for resume."""


@dataclass(frozen=True)
class PreparedRunResume:
    """Surface-independent inputs for resuming a persisted run."""

    run_id: str
    original_task: str
    initial_observations: list[dict[str, Any]]
    initial_context_extra: dict[str, Any] | None = None
    auto_approved_call_id: str | None = None
    pending_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'original_task': self.original_task,
            'initial_observations': self.initial_observations,
            'initial_context_extra': self.initial_context_extra,
            'auto_approved_call_id': self.auto_approved_call_id,
            'pending_warning': self.pending_warning,
        }


def prepare_run_resume(
    root: str | Path,
    run_id: str,
    *,
    approve_call_ids: frozenset[str] = frozenset(),
    fresh_restart: bool = False,
    auto_compact: bool = True,
    checkpoint_path: str | Path | None = None,
    auto_approve_pending: bool = True,
) -> PreparedRunResume:
    """Load task, observations, and pending-approval handling for resume.

    Parameters
    ----------
    auto_approve_pending:
        If ``True`` (default) pending tool calls with a digest are
        auto-approved during resume.  Set to ``False`` to warn instead
        (used by TUI where the user should explicitly approve first).
    """
    store = RunStore(root)
    try:
        original_task = store.task_for_run(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise ResumePreparationError(str(exc)) from exc

    initial_observations: list[dict[str, Any]] = []
    initial_context_extra: dict[str, Any] | None = None
    auto_approved: str | None = None
    pending_warning: str | None = None

    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    approval_store = ApprovalPresetStore(root)

    if not fresh_restart:
        checkpoint = None
        if checkpoint_path:
            from teaagent.checkpoint import SQLiteCheckpointStore

            checkpoint = SQLiteCheckpointStore(checkpoint_path).load(run_id)
        if checkpoint is not None:
            initial_observations = checkpoint.get('observations', [])
            initial_context_extra = {
                k: v for k, v in checkpoint.items() if k not in ('task', 'observations')
            }
        else:
            initial_observations = store.observations_for_run(run_id)
            if auto_compact and len(initial_observations) > 40:
                initial_observations = initial_observations[-20:]
                initial_context_extra = {
                    'resume_compaction': {
                        'truncated': True,
                        'kept_observations': 20,
                    }
                }

        pending = store.pending_approval_for_run(run_id)
        if pending:
            digest = pending.get('argument_digest')
            call_id = pending['call_id']

            # If the caller explicitly pre-approved this call, skip silently
            # — no re-grant, no auto-approval flag, no warning (SURF-010 P0).
            if call_id in approve_call_ids:
                pass
            elif not digest:
                pending_warning = (
                    f"Pending call '{call_id}' is a legacy record and cannot be "
                    f'auto-approved safely due to redacted arguments. '
                    f'Please approve explicitly with --approve-call-id {call_id}.'
                )
            elif auto_approve_pending:
                _ensure_scoped_approval(approval_store, run_id, pending, digest)
                auto_approved = call_id
            else:
                pending_warning = f'run {run_id} has a pending approval'

    return PreparedRunResume(
        run_id=run_id,
        original_task=original_task,
        initial_observations=initial_observations,
        initial_context_extra=initial_context_extra,
        auto_approved_call_id=auto_approved,
        pending_warning=pending_warning,
    )


def _ensure_scoped_approval(
    approval_store: Any,
    run_id: str,
    pending: dict[str, Any],
    digest: str | None,
) -> None:
    """Add a scoped approval for *pending* if one does not already exist."""
    if digest and not approval_store.check_scoped_approval_digest(
        run_id=run_id,
        call_id=pending['call_id'],
        tool_name=pending['tool_name'],
        argument_digest=digest,
    ):
        approval_store.add_scoped_approval(
            run_id=run_id,
            call_id=pending['call_id'],
            tool_name=pending['tool_name'],
            arguments=pending['arguments'],
            argument_digest=digest,
        )
