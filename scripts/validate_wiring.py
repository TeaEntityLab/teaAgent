#!/usr/bin/env python3
"""Validate that every teaagent module is production-reachable or explicitly labeled unwired."""

from __future__ import annotations

import argparse
import ast
import sys
from collections import deque
from pathlib import Path
from typing import NamedTuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEAAGENT_ROOT = _REPO_ROOT / 'teaagent'
_UNWIRED_LABEL = 'experimental — unwired'
_DOCSTRING_SCAN_LINES = 40

# Production entry surfaces used for import-graph reachability.
ENTRY_ROOTS: tuple[str, ...] = (
    'teaagent.cli',
    'teaagent.tui',
    'teaagent.runner',
    'teaagent.gateway',
    'teaagent.jit_approval_server',
    'teaagent.mcp_server',
    'teaagent.mcp_http',
)

# H4/H5/H6 clusters from ENG-R1 — must be production-wired or explicitly labeled.
WATCH_MODULES: tuple[str, ...] = (
    'teaagent.governance.policy_routing',
    'teaagent.consensus.consensus_validation',
    'teaagent.governance.scope_creep',
    'teaagent.governance.repo_map_benchmark',
    'teaagent.update',
    'teaagent.update.changelog',
    'teaagent.update.delta',
    'teaagent.update.installer',
    'teaagent.update.update',
)


class WiringReport(NamedTuple):
    reachable: frozenset[str]
    unreachable: frozenset[str]
    unlabeled: frozenset[str]
    missing_modules: frozenset[str]
    unwired_watch: frozenset[str]


def _module_name_for_path(path: Path) -> str:
    relative = path.relative_to(_TEAAGENT_ROOT)
    if relative.name == '__init__.py':
        parts = relative.parts[:-1]
    else:
        parts = relative.with_suffix('').parts
    return 'teaagent.' + '.'.join(parts) if parts else 'teaagent'


def discover_teaagent_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in sorted(_TEAAGENT_ROOT.rglob('*.py')):
        name = _module_name_for_path(path)
        modules[name] = path
    return modules


def _resolve_import(
    module_name: str,
    node: ast.Import | ast.ImportFrom,
    *,
    current_module: str,
) -> set[str]:
    targets: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            targets.add(alias.name)
        return targets

    if node.level and node.module:
        package_parts = current_module.split('.')
        parent_len = max(0, len(package_parts) - node.level)
        parent = '.'.join(package_parts[:parent_len])
        targets.add(f'{parent}.{node.module}' if parent else node.module)
        return targets

    if node.level and not node.module:
        package_parts = current_module.split('.')
        parent_len = max(0, len(package_parts) - node.level)
        parent = '.'.join(package_parts[:parent_len])
        if parent:
            targets.add(parent)
        return targets

    if node.module:
        targets.add(node.module)
    return targets


def _imports_in_file(path: Path, *, module_name: str) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.update(_resolve_import(module_name, node, current_module=module_name))
    return found


def _expand_to_teaagent_modules(names: set[str], modules: dict[str, Path]) -> set[str]:
    expanded: set[str] = set()
    for name in names:
        if name in modules:
            expanded.add(name)
            continue
        if not name.startswith('teaagent.'):
            continue
        prefix = name + '.'
        for module in modules:
            if module.startswith(prefix) or module == name:
                expanded.add(module)
    return expanded


def _reachable_modules(modules: dict[str, Path]) -> set[str]:
    queue: deque[str] = deque()
    seen: set[str] = set()
    for root in ENTRY_ROOTS:
        if root in modules:
            queue.append(root)
            seen.add(root)
        else:
            prefix = root + '.'
            for module in modules:
                if module.startswith(prefix):
                    queue.append(module)
                    seen.add(module)

    while queue:
        current = queue.popleft()
        path = modules.get(current)
        if path is None:
            continue
        raw_imports = _imports_in_file(path, module_name=current)
        for imported in _expand_to_teaagent_modules(raw_imports, modules):
            if imported not in seen:
                seen.add(imported)
                queue.append(imported)
    return seen


def _has_unwired_label(path: Path) -> bool:
    lines = path.read_text(encoding='utf-8').splitlines()[:_DOCSTRING_SCAN_LINES]
    snippet = '\n'.join(lines)
    return _UNWIRED_LABEL in snippet


def analyze_wiring(*, repo_root: Path | None = None) -> WiringReport:
    global _REPO_ROOT, _TEAAGENT_ROOT
    if repo_root is not None:
        _REPO_ROOT = repo_root
        _TEAAGENT_ROOT = _REPO_ROOT / 'teaagent'

    modules = discover_teaagent_modules()
    reachable = _reachable_modules(modules)
    unreachable = set(modules) - reachable

    unwired_watch = {
        module
        for module in WATCH_MODULES
        if module in modules and module not in reachable
    }

    unlabeled: set[str] = set()
    for module in sorted(unwired_watch):
        if not _has_unwired_label(modules[module]):
            unlabeled.add(module)

    missing_roots = {
        root
        for root in ENTRY_ROOTS
        if root not in modules
        and not any(name.startswith(root + '.') for name in modules)
    }
    # Optional entry roots may be absent in minimal installs.
    optional_roots = frozenset({'teaagent.jit_approval_server'})
    missing_roots -= optional_roots

    return WiringReport(
        reachable=frozenset(reachable),
        unreachable=frozenset(unreachable),
        unlabeled=frozenset(unlabeled),
        missing_modules=frozenset(missing_roots),
        unwired_watch=frozenset(unwired_watch),
    )


def validate_wiring(*, repo_root: Path | None = None) -> list[str]:
    report = analyze_wiring(repo_root=repo_root)
    errors: list[str] = []
    if repo_root is None:
        for root in sorted(report.missing_modules):
            errors.append(f'Entry root module not found: {root}')
    for module in sorted(report.unlabeled):
        errors.append(
            f'Unreachable teaagent module missing {_UNWIRED_LABEL!r} label: {module}'
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--report',
        action='store_true',
        help='Print reachable/unreachable module counts and exit 0.',
    )
    args = parser.parse_args(argv)

    report = analyze_wiring()
    if args.report:
        print(f'reachable={len(report.reachable)}')
        print(f'unwired_watch={len(report.unwired_watch)}')
        print(f'unlabeled={len(report.unlabeled)}')
        for module in sorted(report.unwired_watch):
            label = 'unlabeled' if module in report.unlabeled else 'labeled'
            print(f'  {module} ({label})')
        return 0

    errors = validate_wiring()
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print('Wiring validation passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
