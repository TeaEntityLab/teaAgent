# test-type: contract
"""A-P1-7 (owner decision 2026-10-27, approval split-plan Q3): the duplicate multi-sig
and high-risk path in ``ApprovalPolicy`` is archived, not live.

The live multi-sig path is ``MultiSigQuorumManager`` in ``teaagent/approval/manager.py``.
The archived code is kept under ``docs/archive/code/`` for reference. These checks pin
that the duplicate stays out of ``teaagent.policy``, so it cannot drift back in
unnoticed, and that the live entry points are still present.
"""

from __future__ import annotations

import dataclasses

from teaagent.approval.manager import MultiSigQuorumManager
from teaagent.policy import ApprovalPolicy, compute_scoped_payload_digest

_ARCHIVED_METHODS = (
    '_is_high_risk_operation',
    '_check_command_args',
    '_check_multi_sig_quorum',
    '_generate_approval_hash',
    '_collect_peer_signatures',
    '_run_async_signature_collection',
)


def test_archived_multisig_helpers_are_not_on_approval_policy() -> None:
    present = [name for name in _ARCHIVED_METHODS if hasattr(ApprovalPolicy, name)]
    assert present == []


def test_archived_signature_executor_field_is_removed() -> None:
    field_names = {field.name for field in dataclasses.fields(ApprovalPolicy)}
    assert '_signature_executor' not in field_names


def test_live_multisig_manager_and_scoped_digest_remain() -> None:
    assert callable(MultiSigQuorumManager.check_quorum)
    assert callable(MultiSigQuorumManager.is_high_risk)
    assert (
        len(compute_scoped_payload_digest('workspace_write_file', {'path': 'a'})) == 64
    )
