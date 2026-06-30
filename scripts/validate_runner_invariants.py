#!/usr/bin/env python3
"""Guard the ADR 0040 second-framework invariant: import-path authority.

Checks that the second execution framework (SubagentManager in
subagents/_manager.py, SwarmManager in swarm.py) does not introduce
parallel authority paths for audit or approval.  The framework may
delegate through run_chat_agent (which uses EventSpine internally)
rather than importing EventSpine directly.

Run: python3 scripts/validate_runner_invariants.py
Exit code 0 when clean, 1 on any violation.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Files that constitute the second execution framework per ADR 0040.
_SECOND_FRAMEWORK_FILES: tuple[str, ...] = (
    'teaagent/subagents/_manager.py',
    'teaagent/swarm.py',
)

# Required approval authority: at least one of the listed modules must be
# imported by each file so the second framework does not implement its own
# parallel approval path.
_APPROVAL_IMPORT_OPTIONS: frozenset[str] = frozenset(
    {
        'teaagent.approval.manager',
        'teaagent.subagents._approval_queue',
    }
)

# Required audit authority: at least one of the listed modules must be
# imported.  run_chat_agent uses EventSpine + audit bridge internally,
# so importing chat_agent satisfies the audit invariant.
_AUDIT_IMPORT_OPTIONS: frozenset[str] = frozenset(
    {
        'teaagent.runner._events',
        'teaagent.chat_agent',
        'teaagent.subagents._manager',
    }
)

# ADR 0041 Phase 1 (G2-budget): the subagent path must delegate parent-clamping
# to the canonical invariant rather than re-implementing min(child, parent).
_BUDGET_CLAMP_IMPORT = 'teaagent.runner._invariants'
_BUDGET_CLAMP_SYMBOL = 'compute_clamped_budget'
_BUDGET_CLAMP_FILES: tuple[str, ...] = ('teaagent/subagents/_manager.py',)


def _collect_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            imports.add(module)
    return imports


def _check_file(rel_path: str) -> list[str]:
    file_path = _REPO_ROOT / rel_path
    if not file_path.is_file():
        return [f'{rel_path}: file not found']
    source = file_path.read_text(encoding='utf-8')
    imports = _collect_imports(source)
    errors: list[str] = []

    approval_found = bool(imports & _APPROVAL_IMPORT_OPTIONS)
    if not approval_found:
        errors.append(
            f'{rel_path}: missing approval authority import — '
            f'must import at least one of: '
            f'{", ".join(sorted(_APPROVAL_IMPORT_OPTIONS))}'
        )

    audit_found = bool(imports & _AUDIT_IMPORT_OPTIONS)
    if not audit_found:
        errors.append(
            f'{rel_path}: missing audit authority import — '
            f'must import at least one of: '
            f'{", ".join(sorted(_AUDIT_IMPORT_OPTIONS))}'
        )
    return errors


def _check_budget_clamp_authority(rel_path: str) -> list[str]:
    """ADR 0041 Phase 1 G2: forbid a re-implemented parent budget clamp."""
    file_path = _REPO_ROOT / rel_path
    if not file_path.is_file():
        return [f'{rel_path}: file not found']
    source = file_path.read_text(encoding='utf-8')
    imports = _collect_imports(source)
    if _BUDGET_CLAMP_IMPORT not in imports:
        return [
            f'{rel_path}: missing budget-clamp authority — must import '
            f'{_BUDGET_CLAMP_IMPORT} and call {_BUDGET_CLAMP_SYMBOL} instead of '
            f're-implementing parent budget clamping (ADR 0041 Phase 1, G2)'
        ]
    if _BUDGET_CLAMP_SYMBOL not in source:
        return [
            f'{rel_path}: imports {_BUDGET_CLAMP_IMPORT} but never calls '
            f'{_BUDGET_CLAMP_SYMBOL} (ADR 0041 Phase 1, G2)'
        ]
    return []


def validate() -> list[str]:
    errors: list[str] = []
    for rel_path in _SECOND_FRAMEWORK_FILES:
        errors.extend(_check_file(rel_path))
    for rel_path in _BUDGET_CLAMP_FILES:
        errors.extend(_check_budget_clamp_authority(rel_path))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print('Runner invariants check FAILED:', file=sys.stderr)
        for err in errors:
            print(f'  - {err}', file=sys.stderr)
        return 1
    print('Runner invariants check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
