# test-type: adversarial
"""Executable specification for the H4 shadow-to-enforce promotion hold.

Companion to docs/specs/rbac-shadow-to-enforce-promotion-spec-2026-07-11.md
(roadmap H4, ADR-0031, DR-006 hold: RBAC enforce flip held until owner demand).

These tests make the CURRENT hold executable: they pin shadow-by-default,
fail-safe mode parsing, the shadow receipt schema (the input contract for the
ADR-0031 exit-criterion analysis), and the documented asymmetry between the
policy surface (advisory-only today) and the RBAC surface (enforce
implemented). If the asymmetry pin fails, the policy surface began enforcing:
execute the promotion-day checklist in the spec and update roadmap-status H4
in the same change.
"""

from __future__ import annotations

from typing import Any

import pytest

from teaagent.governance.h4_integration import (
    H4GovernanceMode,
    check_subagent_launch_rbac,
    evaluate_approval_policy_shadow,
    policy_governance_mode,
    rbac_governance_mode,
)
from teaagent.governance.policy_engine import (
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyPrecedence,
    PolicyStore,
    PolicyType,
)

_MODE_ENV_VARS = ('TEAAGENT_H4_POLICY_MODE', 'TEAAGENT_H4_RBAC_MODE')


class _RecordingAudit:
    """Minimal audit stub capturing record() calls for schema assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def record(self, event_type: str, run_id: str, **kwargs: Any) -> None:
        self.calls.append((event_type, run_id, kwargs))


def _clear_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _MODE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _save_deny_all_approval_policy(root: Any) -> None:
    """Persist a policy that denies the approve_tool action at HIGH precedence."""
    store = PolicyStore(root)
    store.save(
        Policy(
            policy_id='spec-deny-approve-tool',
            policy_type=PolicyType.APPROVAL,
            effect=PolicyEffect.DENY,
            conditions=[
                PolicyCondition(field='action', operator='equals', value='approve_tool')
            ],
            precedence=PolicyPrecedence.HIGH,
            description='H4 promotion spec fixture: deny all tool approvals.',
        )
    )


def test_policy_and_rbac_modes_default_to_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no env override, both H4 surfaces resolve to SHADOW.

    Defends the ADR-0031 hold: shadow is the shipped default until the
    promotion checklist runs. A failure here means the default was flipped.
    """
    _clear_mode_env(monkeypatch)
    assert policy_governance_mode() is H4GovernanceMode.SHADOW
    assert rbac_governance_mode() is H4GovernanceMode.SHADOW


def test_invalid_mode_value_falls_back_to_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized mode string fails safe to SHADOW, never to enforce.

    Fail-safe parsing is a promotion precondition: a typo in an env var must
    not silently enable (or disable) enforcement.
    """
    monkeypatch.setenv('TEAAGENT_H4_POLICY_MODE', 'block-everything')
    monkeypatch.setenv('TEAAGENT_H4_RBAC_MODE', 'yes')
    assert policy_governance_mode() is H4GovernanceMode.SHADOW
    assert rbac_governance_mode() is H4GovernanceMode.SHADOW


def test_mode_parsing_normalizes_case_and_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mode values are strip()/lower() normalized before matching.

    Pins h4_integration._mode_from_env semantics so config-file resolution
    (spec section 3.2) can rely on the same normalization contract.
    """
    monkeypatch.setenv('TEAAGENT_H4_POLICY_MODE', '  ENFORCE  ')
    assert policy_governance_mode() is H4GovernanceMode.ENFORCE
    monkeypatch.setenv('TEAAGENT_H4_RBAC_MODE', 'Shadow')
    assert rbac_governance_mode() is H4GovernanceMode.SHADOW


def test_policy_enforce_mode_is_currently_advisory_only(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TEAAGENT_H4_POLICY_MODE=enforce changes only the receipt label today.

    Asymmetry pin (spec section 1): the approval-policy surface has no enforce
    branch — a denying policy still yields return True, with enforced=False in
    the shadow receipt. If this test fails because the call returned False (or
    raised), the policy surface began enforcing: that is the ADR-0031
    promotion, which requires the spec's section 5 checklist (rename, denial
    UX parity, roadmap-status H4 update) in the same change.
    """
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv('TEAAGENT_H4_POLICY_MODE', 'enforce')
    _save_deny_all_approval_policy(tmp_path)
    audit = _RecordingAudit()

    proceeded = evaluate_approval_policy_shadow(
        workspace_root=tmp_path,
        audit=audit,
        run_id='run-spec-h4',
        tool_name='write_file',
        arguments={'path': 'x.txt'},
        destructive=True,
        call_id='call-1',
    )

    assert proceeded is True
    assert len(audit.calls) == 1
    event_type, run_id, payload = audit.calls[0]
    assert event_type == 'h4_governance_shadow'
    assert run_id == 'run-spec-h4'
    assert payload['mode'] == 'enforce'
    assert payload['allowed'] is False
    assert payload['enforced'] is False


def test_shadow_receipt_payload_schema(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The h4_governance_shadow receipt carries the frozen analysis key-set.

    The ADR-0031 30-day false-positive analysis (spec section 3.1) consumes
    exactly {surface, mode, allowed, enforced, reason, context, details}.
    Schema drift here silently breaks the promotion evidence pipeline.
    """
    _clear_mode_env(monkeypatch)
    audit = _RecordingAudit()
    evaluate_approval_policy_shadow(
        workspace_root=tmp_path,
        audit=audit,
        run_id='run-schema',
        tool_name='read_file',
        arguments={},
        destructive=False,
        call_id='call-2',
    )
    _event_type, _run_id, payload = audit.calls[0]
    assert set(payload) == {
        'surface',
        'mode',
        'allowed',
        'enforced',
        'reason',
        'context',
        'details',
    }
    assert payload['surface'] == 'approval'
    assert payload['mode'] == 'shadow'
    assert isinstance(payload['reason'], str) and payload['reason']
    assert isinstance(payload['details'], list)


def test_shadow_mode_never_blocks_denied_action(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under SHADOW a denying policy is recorded but the action proceeds.

    Complement of the enforce-denial coverage in test_h4_shadow_wiring.py:
    shadow mode's whole contract is observe-without-blocking, which is what
    makes the 30-day observation window safe to run in production.
    """
    _clear_mode_env(monkeypatch)
    _save_deny_all_approval_policy(tmp_path)
    audit = _RecordingAudit()

    proceeded = evaluate_approval_policy_shadow(
        workspace_root=tmp_path,
        audit=audit,
        run_id='run-shadow-deny',
        tool_name='write_file',
        arguments={'path': 'y.txt'},
        destructive=True,
        call_id='call-3',
    )

    assert proceeded is True
    _event_type, _run_id, payload = audit.calls[0]
    assert payload['mode'] == 'shadow'
    assert payload['allowed'] is False
    assert payload['enforced'] is False


def test_rbac_enforce_result_consistent_with_receipt(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under ENFORCE the RBAC return value must match the recorded receipt.

    Invariant (survives promotion): the launch proceeds iff the receipt says
    allowed; the receipt's enforced flag is true exactly when a denial was
    enforced. Divergence would make the audit trail lie about what happened —
    the exact failure the H4 receipts exist to prevent. Uses an empty RBAC
    store so the test does not depend on default role fixtures.
    """
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv('TEAAGENT_H4_RBAC_MODE', 'enforce')
    audit = _RecordingAudit()

    allowed, reason = check_subagent_launch_rbac(
        workspace_root=tmp_path,
        audit=audit,
        parent_run_id='parent-spec',
        assignee='spec-operator',
        def_name='scout',
        depth=1,
    )

    assert isinstance(reason, str) and reason
    assert len(audit.calls) == 1
    _event_type, _run_id, payload = audit.calls[0]
    assert payload['surface'] == 'subagent_launch'
    assert payload['mode'] == 'enforce'
    assert allowed == payload['allowed']
    assert payload['enforced'] == (not payload['allowed'])
