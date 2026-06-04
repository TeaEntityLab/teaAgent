from __future__ import annotations

import importlib
import sys


def test_import_policy_then_approval_manager() -> None:
    """Verifies that importing policy first, then approval_manager, does not raise errors."""
    # Clear from sys.modules to force clean load
    sys.modules.pop('teaagent.policy', None)
    sys.modules.pop('teaagent.approval_manager', None)

    policy = importlib.import_module('teaagent.policy')
    approval_manager = importlib.import_module('teaagent.approval_manager')

    assert policy is not None
    assert approval_manager is not None


def test_import_approval_manager_then_policy() -> None:
    """Verifies that importing approval_manager first, then policy, does not raise errors."""
    # Clear from sys.modules to force clean load
    sys.modules.pop('teaagent.policy', None)
    sys.modules.pop('teaagent.approval_manager', None)

    approval_manager = importlib.import_module('teaagent.approval_manager')
    policy = importlib.import_module('teaagent.policy')

    assert approval_manager is not None
    assert policy is not None
