#!/usr/bin/env python3
"""Test quality audit tool.

Analyzes test files for quality metrics including assertions, mocks, skips,
and weak patterns (placeholders, construction-only, mock-only).
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_relative(path: Path) -> str:
    """Return a stable repo-relative path for reports."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def collect_pytest_nodes(tests_dir: Path) -> list[str]:
    """Collect pytest node IDs using pytest --collect-only."""
    tests_dir = tests_dir.resolve()
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only', '-q', str(tests_dir)],
        capture_output=True,
        text=True,
        cwd=tests_dir.parent,
    )

    if result.returncode != 0:
        error_msg = f'pytest collection failed: {result.stderr}'
        print(f'Error: {error_msg}', file=sys.stderr)
        raise RuntimeError(error_msg)

    lines = result.stdout.strip().splitlines()
    nodes: list[str] = []
    for line in lines:
        node_id = line.strip().split()[0] if line.strip() else ''
        if '::' not in node_id:
            continue
        parts = node_id.split('::')
        if any(part.startswith('test_') for part in parts[1:]):
            nodes.append(node_id)

    return nodes


def discover_test_files(tests_dir: Path) -> list[Path]:
    """Discover all Python test files in the directory."""
    if (
        tests_dir.is_file()
        and tests_dir.name.startswith('test_')
        and tests_dir.suffix == '.py'
    ):
        return [tests_dir]
    return list(tests_dir.rglob('test_*.py'))


class FileMetrics:
    """Metrics for a single test file."""

    def __init__(self, path: Path):
        self.path = path
        self.test_functions: list[str] = []
        self.docstrings: dict[str, str] = {}
        self.assertion_counts: dict[str, int] = {}
        self.has_syntax_error = False
        self.weak_patterns: dict[str, list[str]] = {}  # test_name -> list of patterns
        self.skip_decorators: dict[str, bool] = {}  # test_name -> has_skip
        self.skip_reasons: dict[str, bool] = {}  # test_name -> has explicit skip reason
        self.mock_counts: dict[str, int] = {}  # test_name -> mock count
        self.test_type: str = 'contract'  # default test type
        self.test_types_per_function: dict[str, str] = {}  # test_name -> type


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f'{prefix}.{node.attr}' if prefix else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ''


def _decorator_has_reason(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return any(
        keyword.arg == 'reason'
        and isinstance(keyword.value, ast.Constant)
        and bool(keyword.value.value)
        for keyword in node.keywords
    )


def _is_construction_assert_call(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Name):
        return call.func.id == 'isinstance'
    if isinstance(call.func, ast.Attribute):
        return call.func.attr in {
            'assertIsInstance',
            'assertIsNotNone',
        }
    return False


def _is_pytest_context_manager(node: ast.AST) -> bool:
    """Check if node is a pytest.raises/warns/deprecated_call context manager."""
    if not isinstance(node, ast.With):
        return False
    for item in node.items:
        if (
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr in {'raises', 'warns', 'deprecated_call'}
            and isinstance(item.context_expr.func.value, ast.Name)
            and item.context_expr.func.value.id == 'pytest'
        ):
            return True
    return False


def _is_construction_assert_expr(expr: ast.AST) -> bool:
    if isinstance(expr, ast.Call):
        return _is_construction_assert_call(expr)
    if (
        not isinstance(expr, ast.Compare)
        or len(expr.ops) != 1
        or len(expr.comparators) != 1
    ):
        return False

    left = expr.left
    right = expr.comparators[0]
    op = expr.ops[0]
    if (
        isinstance(op, ast.IsNot)
        and isinstance(right, ast.Constant)
        and right.value is None
    ):
        return True
    if isinstance(op, ast.Eq) and isinstance(left, ast.Call):
        return isinstance(left.func, ast.Name) and left.func.id == 'type'
    return False


def scan_test_file(file_path: Path) -> FileMetrics:
    """Scan a test file with AST to extract metrics."""
    metrics = FileMetrics(file_path)

    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(f'Warning: syntax error in {file_path}: {e}', file=sys.stderr)
        metrics.has_syntax_error = True
        return metrics

    # Classify test type based on path and explicit markers
    metrics.test_type = classify_test_type(file_path, source)

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith('test_'):
            test_name = node.name
            metrics.test_functions.append(test_name)

            # Check for skip decorators
            has_skip = False
            has_skip_reason = False
            for decorator in node.decorator_list:
                decorator_name = _decorator_name(decorator)
                if decorator_name.endswith(('skip', 'skipif', 'skipIf')):
                    has_skip = True
                    has_skip_reason = has_skip_reason or _decorator_has_reason(
                        decorator
                    )
            metrics.skip_decorators[test_name] = has_skip
            metrics.skip_reasons[test_name] = has_skip_reason

            # Extract docstring
            docstring = ast.get_docstring(node)
            if docstring:
                metrics.docstrings[test_name] = docstring

            # Count assertions and detect weak patterns
            assert_count = 0
            weak_patterns = []
            mock_count = 0
            pass_only = bool(node.body) and all(
                isinstance(stmt, ast.Pass) for stmt in node.body
            )
            construction_asserts = 0

            for child in ast.walk(node):
                # Count pytest.raises/warns/deprecated_call as assertions
                if _is_pytest_context_manager(child):
                    assert_count += 1

                # Count bare assert statements
                if isinstance(child, ast.Assert):
                    assert_count += 1
                    # Check for assert True
                    if (
                        isinstance(child.test, ast.Constant)
                        and child.test.value is True
                    ):
                        weak_patterns.append('assert_true')
                    if _is_construction_assert_expr(child.test):
                        construction_asserts += 1

                # Count unittest assertion methods (self.assertEqual, etc.)
                if isinstance(child, ast.Call):
                    # Check for unittest assertion methods
                    if isinstance(
                        child.func, ast.Attribute
                    ) and child.func.attr.startswith('assert'):
                        assert_count += 1
                        if _is_construction_assert_call(child):
                            construction_asserts += 1

                    # Count mock usage (Mock, MagicMock, patch)
                    if (
                        isinstance(child.func, ast.Name)
                        and child.func.id in ('Mock', 'MagicMock', 'patch')
                    ) or (
                        isinstance(child.func, ast.Attribute)
                        and child.func.attr in ('Mock', 'MagicMock', 'patch')
                    ):
                        mock_count += 1

            metrics.assertion_counts[test_name] = assert_count
            metrics.mock_counts[test_name] = mock_count

            # Detect weak patterns
            if assert_count == 0:
                weak_patterns.append('no_assertions')
                if pass_only:
                    weak_patterns.append('placeholder')
            elif assert_count == 1 and weak_patterns:
                # Only assert True or similar
                weak_patterns.append('single_weak_assert')

            if mock_count > 0 and assert_count == 0:
                weak_patterns.append('mock_only')

            if assert_count > 0 and assert_count == construction_asserts:
                weak_patterns.append('construction_only')

            if has_skip and not has_skip_reason:
                weak_patterns.append('undocumented_skip')

            if weak_patterns:
                metrics.weak_patterns[test_name] = weak_patterns

    return metrics


def infer_domain(path: Path) -> str:
    path_str = _repo_relative(path)
    for domain in (
        'security',
        'audit',
        'tui',
        'memory',
        'subagent',
        'automation',
        'budget',
        'workspace',
        'policy',
        'cli',
    ):
        if domain in path_str:
            return domain
    return 'general'


def infer_tier(path: Path) -> str:
    path_str = _repo_relative(path)
    if 'security' in path_str or 'audit' in path_str:
        return 'P0'
    if '/acceptance/' in f'/{path_str}':
        return 'P1'
    if '/integration/' in f'/{path_str}':
        return 'P2'
    return 'unit'


def classify_test_type(file_path: Path, source_text: str | None = None) -> str:
    """Classify test type based on path heuristics and optional explicit markers.

    Rules (in precedence order):
    1. If source contains pytest.mark.test_type('<type>'), use that type
    2. If source contains # test-type: <type> comment, use that type
    3. If path contains tests/acceptance/ → "behavior"
    4. If path contains tests/lifecycle/ → "lifecycle"
    5. If filename contains "adversarial" → "adversarial"
    6. Otherwise → "contract" (default)

    Valid types: contract, behavior, adversarial, lifecycle
    """
    # Check for explicit pytestmark or comment override in source
    if source_text:
        for line in source_text.splitlines():
            # Check for pytestmark = pytest.mark.test_type('...')
            if 'pytestmark' in line and 'test_type' in line:
                # Extract type from pytestmark = pytest.mark.test_type('<type>')
                for test_type in ('contract', 'behavior', 'adversarial', 'lifecycle'):
                    if (
                        f"test_type('{test_type}')" in line
                        or f'test_type("{test_type}")' in line
                    ):
                        return test_type

            # Check for # test-type: <type> comment
            if '# test-type:' in line:
                parts = line.split('# test-type:')
                if len(parts) > 1:
                    type_str = parts[1].strip().lower()
                    if type_str in ('contract', 'behavior', 'adversarial', 'lifecycle'):
                        return type_str

    # Apply path heuristics
    path_str = _repo_relative(file_path)

    if '/acceptance/' in f'/{path_str}':
        return 'behavior'

    if '/lifecycle/' in f'/{path_str}':
        return 'lifecycle'

    if 'adversarial' in file_path.name:
        return 'adversarial'

    return 'contract'


def metrics_to_json(all_metrics: list[FileMetrics], total_nodes: int) -> dict[str, Any]:
    """Convert metrics to JSON schema."""
    files_data: list[dict[str, Any]] = []

    for metrics in all_metrics:
        if metrics.has_syntax_error:
            continue

        file_data: dict[str, Any] = {
            'path': _repo_relative(metrics.path),
            'collected_tests': len(metrics.test_functions),
            'test_type': metrics.test_type,
            'domain': infer_domain(metrics.path),
            'tier': infer_tier(metrics.path),
            'purpose_status': 'documented' if metrics.docstrings else 'missing',
            'assertion_profile': {
                'total_assertions': sum(metrics.assertion_counts.values()),
                'avg_assertions_per_test': (
                    sum(metrics.assertion_counts.values()) / len(metrics.test_functions)
                    if metrics.test_functions
                    else 0
                ),
                'tests_with_zero_assertions': sum(
                    1 for count in metrics.assertion_counts.values() if count == 0
                ),
            },
            'skip_profile': {
                'total_skips': sum(metrics.skip_decorators.values()),
                'documented_skip_reasons': sum(metrics.skip_reasons.values()),
            },
            'mock_profile': {
                'total_mocks': sum(metrics.mock_counts.values()),
                'avg_mocks_per_test': (
                    sum(metrics.mock_counts.values()) / len(metrics.test_functions)
                    if metrics.test_functions
                    else 0
                ),
                'mock_only_tests': sum(
                    1
                    for patterns in metrics.weak_patterns.values()
                    if 'mock_only' in patterns
                ),
            },
            'risk_flags': list(
                set(
                    pattern
                    for patterns in metrics.weak_patterns.values()
                    for pattern in patterns
                )
            ),
            'recommended_action': 'none' if not metrics.weak_patterns else 'review',
        }
        files_data.append(file_data)

    return {
        'audit_date': datetime.now(timezone.utc).isoformat(),
        'total_tests': total_nodes,
        'total_files': len([m for m in all_metrics if not m.has_syntax_error]),
        'files': files_data,
        'summary': {
            'high_risk_files': sum(
                1
                for file_data in files_data
                if file_data['tier'] == 'P0' and file_data['risk_flags']
            ),
            'medium_risk_files': sum(1 for f in files_data if f['risk_flags']),
            'placeholder_files': sum(
                1 for f in files_data if 'placeholder' in f['risk_flags']
            ),
            'construction_only_files': sum(
                1 for f in files_data if 'construction_only' in f['risk_flags']
            ),
        },
    }


def metrics_to_markdown(all_metrics: list[FileMetrics], total_nodes: int) -> str:
    """Convert metrics to Markdown report."""
    lines = [
        '# Test Intent Audit',
        '',
        f'**Audit Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%d")}',
        '',
        '## Executive Summary',
        '',
        f'- Total tests collected: {total_nodes}',
        f'- Total test files: {len([m for m in all_metrics if not m.has_syntax_error])}',
        f'- Total test functions: {sum(len(m.test_functions) for m in all_metrics)}',
        f'- Tests with docstrings: {sum(len(m.docstrings) for m in all_metrics)}',
        f'- Total assertions: {sum(sum(m.assertion_counts.values()) for m in all_metrics)}',
        f'- Tests with weak patterns: {sum(len(m.weak_patterns) for m in all_metrics)}',
        f'- Tests with skip decorators: {sum(sum(m.skip_decorators.values()) for m in all_metrics)}',
        f'- Total mock calls: {sum(sum(m.mock_counts.values()) for m in all_metrics)}',
        '',
        '## High-Risk Findings',
        '',
        'Files with tests having no assertions:',
        '',
        '| File | Tests with No Assertions |',
        '|------|---------------------------|',
    ]

    # Add high-risk files (no assertions)
    for metrics in all_metrics:
        no_assert_tests = [
            name for name, count in metrics.assertion_counts.items() if count == 0
        ]
        if no_assert_tests:
            lines.append(f'| {_repo_relative(metrics.path)} | {len(no_assert_tests)} |')

    # Add per-type summary
    lines.extend(
        [
            '',
            '## Per-Type Summary',
            '',
            '| Type | Files | Test Functions |',
            '|------|-------|----------------|',
        ]
    )

    # Calculate per-type statistics
    type_stats: dict[str, tuple[int, int]] = {}  # type -> (file_count, test_count)
    for metrics in all_metrics:
        if metrics.has_syntax_error:
            continue
        test_type = metrics.test_type
        file_count, test_count = type_stats.get(test_type, (0, 0))
        type_stats[test_type] = (
            file_count + 1,
            test_count + len(metrics.test_functions),
        )

    for test_type in ('contract', 'behavior', 'adversarial', 'lifecycle'):
        if test_type in type_stats:
            file_count, test_count = type_stats[test_type]
            lines.append(f'| {test_type} | {file_count} | {test_count} |')

    lines.extend(
        [
            '',
            '## Per-File Audit',
            '',
            '| File | Type | Tests | Docstrings | Assertions | Avg Asserts/Test | Mocks | Risk Flags |',
            '|------|------|-------|------------|------------|-----------------|-------|------------|',
        ]
    )

    # Add per-file metrics
    for metrics in all_metrics:
        if metrics.has_syntax_error:
            continue

        risk_flags = (
            ','.join(
                set(
                    pattern
                    for patterns in metrics.weak_patterns.values()
                    for pattern in patterns
                )
            )
            if metrics.weak_patterns
            else 'none'
        )

        lines.append(
            f'| {_repo_relative(metrics.path)} | '
            f'{metrics.test_type} | '
            f'{len(metrics.test_functions)} | '
            f'{len(metrics.docstrings)} | '
            f'{sum(metrics.assertion_counts.values())} | '
            f'{sum(metrics.assertion_counts.values()) / len(metrics.test_functions) if metrics.test_functions else 0:.1f} | '
            f'{sum(metrics.mock_counts.values())} | '
            f'{risk_flags} |'
        )

    lines.extend(
        [
            '',
            '## Remediation Queue',
            '',
            'Prioritized by risk (security/audit paths first, then P0 acceptance, then others):',
            '',
            '| Priority | File | Issue | Action |',
            '|----------|------|-------|--------|',
        ]
    )

    # Add remediation queue (prioritized by path patterns)
    remediation_items = []

    for metrics in all_metrics:
        if metrics.has_syntax_error:
            continue

        path_str = _repo_relative(metrics.path)

        # Determine priority based on path
        priority = 'P3'
        if 'security' in path_str or 'audit' in path_str:
            priority = 'P0'
        elif 'acceptance' in path_str:
            priority = 'P1'
        elif 'integration' in path_str:
            priority = 'P2'

        # Determine issue and action
        no_assert_count = sum(
            1 for count in metrics.assertion_counts.values() if count == 0
        )
        if no_assert_count > 0:
            issue = f'{no_assert_count} tests with no assertions'
            action = 'Add behavior assertions'
            remediation_items.append((priority, path_str, issue, action))

    # Sort by priority
    priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    remediation_items.sort(key=lambda x: (priority_order[x[0]], x[1]))

    # Add top 20 items to avoid overwhelming the report
    for priority, path_str, issue, action in remediation_items[:20]:
        lines.append(f'| {priority} | {path_str} | {issue} | {action} |')

    if len(remediation_items) > 20:
        lines.append(f'| ... | {len(remediation_items) - 20} more files | ... | ... |')

    lines.extend(
        [
            '',
            '## Methodology',
            '',
            'This audit uses AST analysis to scan test files for:',
            '- Test function discovery',
            '- Docstring presence',
            '- Assertion counting',
            '- Mock usage detection',
            '- Weak pattern identification (no assertions, assert True, mock-only, construction-only, undocumented skip)',
            '',
            'Weak patterns detected:',
            '- `no_assertions`: Test functions with zero assert statements',
            '- `placeholder`: Test functions whose body is only `pass`',
            '- `assert_true`: Tests using `assert True` without meaningful checks',
            '- `mock_only`: Tests with mocks but no state/output assertions',
            '- `construction_only`: Tests whose assertions only prove object construction or truthiness',
            '- `undocumented_skip`: Skipped tests without an explicit pytest skip reason',
            '',
            '## Next Steps',
            '',
            '1. Review files with high-risk findings',
            '2. Add behavior assertions to construction-only tests',
            '3. Document skip reasons for optional dependencies',
            '4. Remove or implement placeholder tests',
        ]
    )

    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit test quality')
    parser.add_argument(
        '--tests-dir',
        type=Path,
        default=Path('tests'),
        help='Directory containing tests (default: tests)',
    )
    parser.add_argument(
        '--format',
        choices=['json', 'markdown'],
        default='markdown',
        help='Output format (default: markdown)',
    )
    parser.add_argument(
        '--output', type=Path, help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '--fail-on',
        choices=['none', 'severe'],
        default='none',
        help='Exit non-zero when severe findings are present. Default is report-only.',
    )

    args = parser.parse_args()

    if not args.tests_dir.exists():
        print(f'Error: test directory not found: {args.tests_dir}', file=sys.stderr)
        return 1

    # Collect pytest nodes
    nodes = collect_pytest_nodes(args.tests_dir)
    print(f'Collected {len(nodes)} test nodes', file=sys.stderr)

    # Discover test files
    test_files = discover_test_files(args.tests_dir)
    print(f'Discovered {len(test_files)} test files', file=sys.stderr)

    # Scan test files with AST
    all_metrics = []
    for test_file in test_files:
        metrics = scan_test_file(test_file)
        all_metrics.append(metrics)

    print(f'Scanned {len(all_metrics)} test files', file=sys.stderr)

    # Print summary for verification
    total_tests = sum(len(m.test_functions) for m in all_metrics)
    total_with_docstrings = sum(len(m.docstrings) for m in all_metrics)
    total_assertions = sum(sum(m.assertion_counts.values()) for m in all_metrics)

    print(f'Total test functions: {total_tests}', file=sys.stderr)
    print(f'Tests with docstrings: {total_with_docstrings}', file=sys.stderr)
    print(f'Total assertions: {total_assertions}', file=sys.stderr)

    # Summary of weak patterns
    total_weak = sum(len(m.weak_patterns) for m in all_metrics)
    total_skips = sum(sum(m.skip_decorators.values()) for m in all_metrics)
    total_mocks = sum(sum(m.mock_counts.values()) for m in all_metrics)

    print(f'Tests with weak patterns: {total_weak}', file=sys.stderr)
    print(f'Tests with skip decorators: {total_skips}', file=sys.stderr)
    print(f'Total mock calls: {total_mocks}', file=sys.stderr)

    severe_findings = [
        (_repo_relative(metrics.path), test_name, patterns)
        for metrics in all_metrics
        for test_name, patterns in metrics.weak_patterns.items()
        if (
            'placeholder' in patterns
            or 'mock_only' in patterns
            or (
                (
                    'security' in _repo_relative(metrics.path)
                    or 'audit' in _repo_relative(metrics.path)
                )
                and 'no_assertions' in patterns
            )
        )
    ]

    # Generate output
    if args.format == 'json':
        json_data = metrics_to_json(all_metrics, len(nodes))
        if args.output:
            args.output.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
            print(f'JSON report written to {args.output}', file=sys.stderr)
        else:
            print(json.dumps(json_data, indent=2))
    elif args.format == 'markdown':
        markdown_data = metrics_to_markdown(all_metrics, len(nodes))
        if args.output:
            args.output.write_text(markdown_data, encoding='utf-8')
            print(f'Markdown report written to {args.output}', file=sys.stderr)
        else:
            print(markdown_data)

    if args.fail_on == 'severe' and severe_findings:
        print(f'Severe test quality findings: {len(severe_findings)}', file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
