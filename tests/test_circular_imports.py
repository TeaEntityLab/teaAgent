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


def test_runner_approval_helper_is_not_named_approval_manager() -> None:
    """P0-TR-002 guard: only the canonical policy engine owns ApprovalManager."""
    runner_approval = importlib.import_module('teaagent.runner._approval_manager')

    assert hasattr(runner_approval, 'RunnerApprovalCoordinator')
    assert not hasattr(runner_approval, 'ApprovalManager')


def test_memory_catalog_canonical_export_path() -> None:
    """P0-TR-004 guard: public and legacy imports resolve to one implementation."""
    from teaagent import MemoryCatalog as package_memory_catalog
    from teaagent.memory import MemoryCatalog as public_memory_catalog
    from teaagent.memory.catalog import MemoryCatalog as canonical_memory_catalog
    from teaagent.memory_legacy import MemoryCatalog as legacy_memory_catalog

    assert public_memory_catalog is canonical_memory_catalog
    assert package_memory_catalog is canonical_memory_catalog
    assert legacy_memory_catalog is canonical_memory_catalog
