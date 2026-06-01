#!/usr/bin/env python3
"""Evaluate repo-map quality against a benchmark dataset.

Usage:
  python3 scripts/repo_map_benchmark.py [--repo PATH] [--output report.json]

Output:
  JSON report with:
  - symbol_count: total symbols found
  - mapped_count: symbols in repo map
  - coverage_pct: mapped / total
  - accuracy_pct: correctly resolved / attempted
  - errors: list of resolution failures
  - duration_seconds: time to build and evaluate
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REPO = _REPO_ROOT / 'tests' / 'test_data' / 'repo_map'

_CODE_SUFFIXES = frozenset({'.py', '.pyi'})


def _is_python_file(path: Path) -> bool:
    return path.suffix in _CODE_SUFFIXES and path.name != '__pycache__'


def _extract_symbols_from_file(file_path: Path) -> list[dict[str, Any]]:
    """Parse a Python file with AST and return top-level symbols."""
    symbols: list[dict[str, Any]] = []
    try:
        source = file_path.read_text(encoding='utf-8')
    except Exception:
        return symbols

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return symbols

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            symbols.append(
                {
                    'name': node.name,
                    'kind': 'function',
                    'file': str(file_path),
                    'lineno': node.lineno,
                    'docstring': ast.get_docstring(node) or '',
                }
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                {
                    'name': node.name,
                    'kind': 'async_function',
                    'file': str(file_path),
                    'lineno': node.lineno,
                    'docstring': ast.get_docstring(node) or '',
                }
            )
        elif isinstance(node, ast.ClassDef):
            methods: list[str] = []
            for body_node in node.body:
                if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(body_node.name)
            symbols.append(
                {
                    'name': node.name,
                    'kind': 'class',
                    'file': str(file_path),
                    'lineno': node.lineno,
                    'methods': methods,
                    'docstring': ast.get_docstring(node) or '',
                }
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append(
                        {
                            'name': target.id,
                            'kind': 'variable',
                            'file': str(file_path),
                            'lineno': node.lineno,
                            'docstring': '',
                        }
                    )

    return symbols


def build_repo_map(repo_path: Path) -> dict[str, Any]:
    """Walk a repo and extract all symbols from Python files."""
    all_symbols: list[dict[str, Any]] = []
    files_scanned = 0
    errors: list[dict[str, str]] = []

    for py_file in sorted(repo_path.rglob('*.py')):
        if not _is_python_file(py_file):
            continue
        files_scanned += 1
        try:
            file_symbols = _extract_symbols_from_file(py_file)
            all_symbols.extend(file_symbols)
        except Exception as exc:
            errors.append(
                {
                    'file': str(py_file),
                    'error': str(exc),
                }
            )

    module_structure: dict[str, list[str]] = {}
    for sym in all_symbols:
        rel = Path(sym['file']).relative_to(repo_path)
        module_name = str(rel.with_suffix('')).replace('/', '.')
        module_structure.setdefault(module_name, []).append(sym['name'])

    return {
        'symbols': all_symbols,
        'module_structure': module_structure,
        'files_scanned': files_scanned,
        'parse_errors': errors,
    }


def _build_expected_symbols(repo_path: Path) -> set[str]:
    """Collect expected symbol names from __all__ exports or discovered symbols."""
    init_file = repo_path / '__init__.py'
    if not init_file.exists():
        # Fallback: discover all top-level names from all files
        repo_map = build_repo_map(repo_path)
        return {s['name'] for s in repo_map['symbols']}

    source = init_file.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(init_file))

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == '__all__'
                    and isinstance(node.value, ast.List)
                ):
                    result: set[str] = set()
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            result.add(elt.value)
                    return result

    # Fallback
    repo_map = build_repo_map(repo_path)
    return {s['name'] for s in repo_map['symbols']}


def evaluate_repo_map(repo_path: Path) -> dict[str, Any]:
    """Build a repo map and evaluate against expected symbols."""
    start = time.monotonic()

    repo_map = build_repo_map(repo_path)
    expected = _build_expected_symbols(repo_path)

    mapped_names = {s['name'] for s in repo_map['symbols']}
    total_expected = len(expected)

    if total_expected == 0:
        coverage_pct = 0.0
    else:
        coverage_pct = len(mapped_names & expected) / total_expected * 100

    resolved = len(mapped_names & expected)
    total_mapped = len(mapped_names)
    accuracy_pct = (resolved / total_mapped * 100) if total_mapped > 0 else 0.0

    missing = sorted(expected - mapped_names)
    extra = sorted(mapped_names - expected)

    duration = time.monotonic() - start

    return {
        'symbol_count': total_expected,
        'mapped_count': total_mapped,
        'coverage_pct': round(coverage_pct, 2),
        'accuracy_pct': round(accuracy_pct, 2),
        'resolved_count': resolved,
        'missing_symbols': missing,
        'extra_symbols': extra,
        'parse_errors': repo_map['parse_errors'],
        'files_scanned': repo_map['files_scanned'],
        'duration_seconds': round(duration, 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Evaluate repo-map quality against a benchmark dataset.',
    )
    parser.add_argument(
        '--repo',
        type=Path,
        default=_DEFAULT_REPO,
        help='Path to repo to benchmark (default: tests/test_data/repo_map)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Write JSON report to file (default: stdout)',
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output',
    )
    args = parser.parse_args(argv)

    if not args.repo.is_dir():
        print(f'Error: repo path does not exist: {args.repo}', file=sys.stderr)
        return 1

    report = evaluate_repo_map(args.repo)

    indent = 2 if args.pretty else None
    json_output = json.dumps(report, indent=indent, sort_keys=bool(args.pretty))

    if args.output:
        args.output.write_text(json_output, encoding='utf-8')
        print(f'Report written to {args.output}')
    else:
        print(json_output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
