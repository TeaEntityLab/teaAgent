"""Compatibility tests for the approval module migration (A-P1-4 / ADR-0030).

Asserts that importing from the legacy root-level paths and the new
``teaagent.approval`` subpackage locations yields the same objects.
"""

from __future__ import annotations

import importlib
import typing

import pytest

# ---------------------------------------------------------------------------
# manager
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'symbol',
    [
        'ApprovalManager',
        'ApprovalStoreManager',
        'JITApprovalManager',
        'JITApprovalState',
        'MultiSigQuorumConfig',
        'MultiSigQuorumManager',
        'PeerSignature',
        'PermissionMode',
        'PermissionModeEnforcer',
        'format_denial_message',
        'is_protected_skill_path',
        '_verify_ssh_signature',
        '_normalize_shell_arg',
        '_is_skill_dev_opt_in',
        '_SSH_VERIFICATION_IMPLEMENTED',
    ],
)
def test_manager_symbols_identical(symbol: str) -> None:
    """Each public/private symbol is the same object from both paths."""
    old = importlib.import_module('teaagent.approval_manager')
    new = importlib.import_module('teaagent.approval.manager')
    assert hasattr(old, symbol), f'legacy approval_manager missing {symbol}'
    assert hasattr(new, symbol), f'new approval.manager missing {symbol}'
    assert getattr(old, symbol) is getattr(new, symbol), (
        f'{symbol} differs between legacy and new locations'
    )


def test_manager_module_identity() -> None:
    """The legacy module re-exports from the canonical location."""
    import teaagent.approval.manager as new
    import teaagent.approval_manager as old

    # ApprovalManager is defined in the new module; the old module
    # must expose the exact same class object.
    assert old.ApprovalManager is new.ApprovalManager
    assert old.PermissionMode is new.PermissionMode


# ---------------------------------------------------------------------------
# backend
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'symbol',
    [
        'ApprovalBackend',
        'ApprovalDecision',
        'ApprovalRequest',
        'AllowBackend',
        'DangerFullAccessBackend',
        'PromptBackend',
        'ReadOnlyBackend',
        'WorkspaceWriteBackend',
        'backend_from_mode',
    ],
)
def test_backend_symbols_identical(symbol: str) -> None:
    old = importlib.import_module('teaagent.approval_backend')
    new = importlib.import_module('teaagent.approval.backend')
    assert hasattr(old, symbol), f'legacy approval_backend missing {symbol}'
    assert hasattr(new, symbol), f'new approval.backend missing {symbol}'
    assert getattr(old, symbol) is getattr(new, symbol)


def test_backend_from_mode_works() -> None:
    from teaagent.approval.backend import backend_from_mode
    from teaagent.approval.manager import PermissionMode

    backend = backend_from_mode(PermissionMode.PROMPT)
    assert backend is not None


# ---------------------------------------------------------------------------
# selectors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'symbol',
    [
        'PendingApprovalView',
        'classify_risk_class',
        'collect_pending_approval_views',
        'format_pending_approvals',
        'pending_approvals_payload',
        'resolve_selector',
        'summarize_tool_arguments',
        '_parse_event_timestamp',
    ],
)
def test_selectors_symbols_identical(symbol: str) -> None:
    old = importlib.import_module('teaagent.approval_selectors')
    new = importlib.import_module('teaagent.approval.selectors')
    assert hasattr(old, symbol), f'legacy approval_selectors missing {symbol}'
    assert hasattr(new, symbol), f'new approval.selectors missing {symbol}'
    assert getattr(old, symbol) is getattr(new, symbol)


# ---------------------------------------------------------------------------
# ui
# ---------------------------------------------------------------------------


def test_ui_symbols_identical() -> None:
    old = importlib.import_module('teaagent.approval_ui')
    new = importlib.import_module('teaagent.approval.ui')
    assert old.DiffApprovalHandler is new.DiffApprovalHandler


# ---------------------------------------------------------------------------
# package facade
# ---------------------------------------------------------------------------


def test_package_facade_reexports() -> None:
    """``teaagent.approval`` facade exposes the key symbols."""
    import teaagent.approval as pkg

    assert (
        pkg.ApprovalManager
        is importlib.import_module('teaagent.approval.manager').ApprovalManager
    )
    assert (
        pkg.DiffApprovalHandler
        is importlib.import_module('teaagent.approval.ui').DiffApprovalHandler
    )
    assert (
        pkg.ApprovalBackend
        is importlib.import_module('teaagent.approval.backend').ApprovalBackend
    )
    assert (
        pkg.PermissionMode
        is importlib.import_module('teaagent.approval.manager').PermissionMode
    )


def test_cross_module_permission_mode_identity() -> None:
    """PermissionMode is the same enum whether accessed via manager or backend."""
    from teaagent.approval.backend import ApprovalRequest
    from teaagent.approval.manager import PermissionMode

    hints = typing.get_type_hints(ApprovalRequest)
    assert hints['permission_mode'] is PermissionMode


def test_legacy_imports_work_unchanged() -> None:
    """The exact import patterns used by existing code must still work."""
    from teaagent.approval_backend import ApprovalBackend  # noqa: F401
    from teaagent.approval_manager import ApprovalManager  # noqa: F401
    from teaagent.approval_selectors import (  # noqa: F401
        collect_pending_approval_views,
    )
    from teaagent.approval_ui import DiffApprovalHandler  # noqa: F401
