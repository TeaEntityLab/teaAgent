"""Deprecated root-module import aliases (WDF-002)."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from types import ModuleType

_DEPRECATED_ALIASES: dict[str, str] = {
    'teaagent.approval_backend': 'teaagent.approval.backend',
    'teaagent.approval_manager': 'teaagent.approval.manager',
    'teaagent.approval_selectors': 'teaagent.approval.selectors',
    'teaagent.approval_ui': 'teaagent.approval.ui',
    'teaagent.policy_engine': 'teaagent.governance.policy_engine',
    'teaagent.rbac': 'teaagent.governance.rbac',
    'teaagent.policy_routing': 'teaagent.governance.policy_routing',
    'teaagent.scope_creep': 'teaagent.governance.scope_creep',
    'teaagent.release_gate': 'teaagent.governance.release_gate',
    'teaagent.repo_map_benchmark': 'teaagent.governance.repo_map_benchmark',
    'teaagent.consensus_validation': 'teaagent.consensus.consensus_validation',
}


class _DeprecatedModuleLoader(importlib.abc.Loader):
    def __init__(self, target: str) -> None:
        self._target = target

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        del spec
        return importlib.import_module(self._target)

    def exec_module(self, module: ModuleType) -> None:
        del module


class _DeprecatedAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del path, target
        target_name = _DEPRECATED_ALIASES.get(fullname)
        if target_name is None:
            return None
        return importlib.util.spec_from_loader(
            fullname,
            _DeprecatedModuleLoader(target_name),
        )


def install_deprecated_module_aliases() -> None:
    if any(isinstance(finder, _DeprecatedAliasFinder) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _DeprecatedAliasFinder())
