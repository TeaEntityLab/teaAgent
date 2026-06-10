"""WDF-002 import compatibility for folded H4/H5 modules."""

from __future__ import annotations

import importlib

import pytest

_CANONICAL_IMPORTS: tuple[tuple[str, str], ...] = (
    ('teaagent.governance.policy_engine', 'PolicyEngine'),
    ('teaagent.governance.rbac', 'RBACSystem'),
    ('teaagent.governance.policy_routing', 'PolicyRouter'),
    ('teaagent.governance.scope_creep', 'ScopeCreepDetector'),
    ('teaagent.governance.release_gate', 'ReleaseGate'),
    ('teaagent.governance.repo_map_benchmark', 'RepoMapBenchmark'),
    ('teaagent.consensus.consensus_validation', 'ConsensusValidator'),
)

_DEPRECATED_IMPORTS: tuple[tuple[str, str], ...] = (
    ('teaagent.policy_engine', 'PolicyEngine'),
    ('teaagent.rbac', 'RBACSystem'),
    ('teaagent.policy_routing', 'PolicyRouter'),
    ('teaagent.scope_creep', 'ScopeCreepDetector'),
    ('teaagent.release_gate', 'ReleaseGate'),
    ('teaagent.repo_map_benchmark', 'RepoMapBenchmark'),
    ('teaagent.consensus_validation', 'ConsensusValidator'),
)


@pytest.mark.parametrize(('module_name', 'symbol'), _CANONICAL_IMPORTS)
def test_canonical_import_paths(module_name: str, symbol: str) -> None:
    module = importlib.import_module(module_name)
    assert hasattr(module, symbol)


@pytest.mark.parametrize(('module_name', 'symbol'), _DEPRECATED_IMPORTS)
def test_deprecated_root_import_aliases(module_name: str, symbol: str) -> None:
    importlib.invalidate_caches()
    module = importlib.import_module(module_name)
    assert hasattr(module, symbol)
