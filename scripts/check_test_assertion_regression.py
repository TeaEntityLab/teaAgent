#!/usr/bin/env python3
"""A1 governance gate: fail when a change weakens or deletes existing test assertions.

Implements the "test files are effectively read-only" environment constraint from the
Governed Agentic Engineering framework (governance/AGENT_RULES.md, Roadmap A1). The point
is to stop reward-hacking by deleting/weakening tests to make a change go green.

How it works:
  - For every changed test file, AST-count the assertion strength of each ``test_*``
    function in the BASE revision and in the HEAD (working tree) revision.
  - "Assertion strength" = number of ``assert`` statements + ``self.assert*`` / ``self.fail``
    calls + ``pytest.raises`` / ``pytest.warns`` calls inside the function.
  - A test that existed in base and is now **deleted**, or whose assertion count **dropped**,
    is a regression. New tests and added assertions are always fine.

Override (escape hatch, mirrors the repo's Lore-trailer culture):
  - env ``ALLOW_TEST_WEAKENING=1``, or
  - a ``Allow-test-weakening: <reason>`` trailer in the HEAD commit message.
Either downgrades violations to warnings and exits 0. Use it for genuine refactors/renames
and pair it with a ``Requires Human Review`` sign-off per governance/AGENT_RULES.md.

Usage:
  python3 scripts/check_test_assertion_regression.py                 # compare worktree vs HEAD
  python3 scripts/check_test_assertion_regression.py --base origin/main
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from dataclasses import dataclass

_ASSERT_CALL_NAMES = ('raises', 'warns', 'raises_group')


def _is_assert_call(node: ast.Call) -> bool:
    """True for self.assert*/self.fail(...) and pytest.raises/warns(...)."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    attr = func.attr
    if attr.startswith('assert') or attr == 'fail':
        return True
    if attr in _ASSERT_CALL_NAMES and isinstance(func.value, ast.Name):
        return func.value.id == 'pytest'
    return False


def _count_assertions(node: ast.AST) -> int:
    """Count assertion-bearing statements anywhere inside a function node."""
    total = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert) or (
            isinstance(child, ast.Call) and _is_assert_call(child)
        ):
            total += 1
    return total


def count_assertions_by_function(source: str) -> dict[str, int]:
    """Map qualified test-function name -> assertion count. Git-independent (testable).

    Qualified name is ``Class.method`` for methods, bare ``func`` for module-level tests.
    Only functions whose name starts with ``test`` are considered.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    counts: dict[str, int] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f'{prefix}{child.name}.')
            # Nested defs are not recursed into; their asserts belong to the parent test.
            elif isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and child.name.startswith('test'):
                counts[f'{prefix}{child.name}'] = _count_assertions(child)

    visit(tree, '')
    return counts


@dataclass(frozen=True)
class Regression:
    file: str
    function: str
    kind: str  # 'deleted' | 'weakened'
    base_count: int
    head_count: int

    def describe(self) -> str:
        if self.kind == 'deleted':
            return (
                f'{self.file}::{self.function} was DELETED '
                f'(had {self.base_count} assertion(s))'
            )
        return (
            f'{self.file}::{self.function} WEAKENED '
            f'({self.base_count} -> {self.head_count} assertion(s))'
        )


def find_regressions(
    file: str, base_src: str, head_src: str | None
) -> list[Regression]:
    """Compare base vs head sources for one file. head_src=None means file deleted."""
    base = count_assertions_by_function(base_src)
    head = count_assertions_by_function(head_src) if head_src is not None else {}
    out: list[Regression] = []
    for func, base_count in base.items():
        if base_count == 0:
            continue  # a test with no assertions can't regress; audit_test_quality covers those
        if func not in head:
            out.append(Regression(file, func, 'deleted', base_count, 0))
        elif head[func] < base_count:
            out.append(Regression(file, func, 'weakened', base_count, head[func]))
    return out


# --- git plumbing (kept separate from the pure core above) ---


def _git(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(['git', *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout


def _changed_test_files(base: str) -> list[str]:
    code, out = _git(['diff', '--name-only', base, '--', 'tests/'])
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip().endswith('.py')]


def _base_source(base: str, path: str) -> str | None:
    code, out = _git(['show', f'{base}:{path}'])
    return out if code == 0 else None


def _head_source(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _override_active() -> str | None:
    """Return the override reason if weakening is explicitly allowed, else None."""
    if os.environ.get('ALLOW_TEST_WEAKENING') == '1':
        return 'env ALLOW_TEST_WEAKENING=1'
    code, msg = _git(['log', '-1', '--pretty=%B'])
    if code == 0:
        for line in msg.splitlines():
            if line.lower().startswith('allow-test-weakening:'):
                reason = line.split(':', 1)[1].strip()
                return f'commit trailer: {reason or "(no reason given)"}'
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--base',
        default=os.environ.get('A1_BASE_REF', 'HEAD'),
        help='git ref to compare against (default: HEAD, or $A1_BASE_REF)',
    )
    args = parser.parse_args(argv)

    regressions: list[Regression] = []
    for path in _changed_test_files(args.base):
        base_src = _base_source(args.base, path)
        if base_src is None:
            continue  # newly added file — nothing to regress against
        regressions.extend(find_regressions(path, base_src, _head_source(path)))

    if not regressions:
        print('✅ No weakened or deleted test assertions detected.')
        return 0

    override = _override_active()
    label = '⚠️  (override active)' if override else '❌'
    print(
        f'{label} Test assertion regression check found {len(regressions)} issue(s) '
        f'vs {args.base}:',
        file=sys.stderr,
    )
    for reg in regressions:
        print(f'  - {reg.describe()}', file=sys.stderr)

    if override:
        print(
            f'\nOverride accepted ({override}); downgraded to warning.', file=sys.stderr
        )
        return 0

    print(
        '\nWeakening or deleting existing tests is Forbidden by governance/AGENT_RULES.md.\n'
        'If this is a legitimate refactor/rename, get a Requires-Human-Review sign-off and\n'
        'set ALLOW_TEST_WEAKENING=1 or add an "Allow-test-weakening: <reason>" commit trailer.',
        file=sys.stderr,
    )
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
