# test-type: contract
"""Facade surface pins for the approval manager split (A-P1-6, ADR-0044).

``teaagent.approval.manager`` is the stable import target while the module is split
into ``teaagent.approval._*`` modules. These tests pin:

- the public surface (``__all__``) as a list, not a count;
- the private names that production code, tests and ``teaagent.policy`` import from
  the facade;
- object identity for those names across the import paths that reach them.

They must keep passing, unedited, after every move step.
"""

from __future__ import annotations

import importlib

import pytest

_FACADE = 'teaagent.approval.manager'

# manager.__all__ at the start of the split (main, 2026-10-28).
EXPECTED_ALL = frozenset(
    {
        'ApprovalManager',
        'ApprovalRequest',
        'PeerApprovalRequest',
        'ApprovalStoreManager',
        'JITApprovalManager',
        'JITApprovalState',
        'MultiSigQuorumConfig',
        'MultiSigQuorumManager',
        'PeerSignature',
        'PermissionMode',
        'PermissionModeEnforcer',
        '_verify_ssh_signature',
        '_normalize_shell_arg',
        'format_denial_message',
        'is_protected_skill_path',
    }
)

# Private names imported from the facade by production code, tests and scripts.
PRIVATE_FACADE_NAMES = frozenset(
    {
        '_SSH_VERIFICATION_IMPLEMENTED',
        '_JIT_APPROVAL_TIMEOUT_SECONDS',
        '_is_skill_dev_opt_in',
    }
)

# Names teaagent.policy re-exports from the facade.
POLICY_REEXPORTS = frozenset(
    {
        'ApprovalManager',
        'JITApprovalState',
        'MultiSigQuorumConfig',
        'PermissionMode',
        '_normalize_shell_arg',
        '_verify_ssh_signature',
    }
)


def test_facade_all_is_the_pinned_list() -> None:
    manager = importlib.import_module(_FACADE)
    assert set(manager.__all__) == EXPECTED_ALL
    assert len(manager.__all__) == len(set(manager.__all__))


@pytest.mark.parametrize('name', sorted(EXPECTED_ALL | PRIVATE_FACADE_NAMES))
def test_facade_exposes_name(name: str) -> None:
    manager = importlib.import_module(_FACADE)
    assert hasattr(manager, name), f'{_FACADE} no longer exposes {name}'


# teaagent.approval.ApprovalRequest is deliberately the runner-level type (see
# approval/__init__.py), so only names mapped to the facade module are compared.
_LAZY_EXPORTED = sorted(
    name
    for name in EXPECTED_ALL | PRIVATE_FACADE_NAMES
    if importlib.import_module('teaagent.approval')._EXPORTS.get(name, ('', ''))[0]  # type: ignore[attr-defined]
    == _FACADE
)


@pytest.mark.parametrize('name', _LAZY_EXPORTED)
def test_lazy_approval_package_resolves_to_facade_object(name: str) -> None:
    manager = importlib.import_module(_FACADE)
    approval = importlib.import_module('teaagent.approval')
    assert getattr(approval, name) is getattr(manager, name)


@pytest.mark.parametrize('name', sorted(POLICY_REEXPORTS))
def test_policy_reexport_is_the_facade_object(name: str) -> None:
    manager = importlib.import_module(_FACADE)
    policy = importlib.import_module('teaagent.policy')
    assert getattr(policy, name) is getattr(manager, name)


def test_legacy_approval_manager_path_is_the_facade_module() -> None:
    assert importlib.import_module(
        'teaagent.approval_manager'
    ) is importlib.import_module(_FACADE)
