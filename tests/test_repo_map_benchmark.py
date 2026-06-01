"""Tests for repo_map_benchmark script and evaluation logic."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / 'scripts' / 'repo_map_benchmark.py'
_TEST_REPO = _REPO_ROOT / 'tests' / 'test_data' / 'repo_map'


def _run_benchmark(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), *extra_args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return result.stdout.strip()


def test_script_runs_without_errors() -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), '--repo', str(_TEST_REPO)],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f'stderr: {result.stderr}'


def test_output_is_valid_json() -> None:
    output = _run_benchmark('--repo', str(_TEST_REPO))
    report = json.loads(output)
    assert isinstance(report, dict)
    required_keys = {
        'symbol_count', 'mapped_count', 'coverage_pct',
        'accuracy_pct', 'duration_seconds',
    }
    missing = required_keys - set(report.keys())
    assert not missing, f'Missing keys: {missing}'


def test_coverage_pct_is_valid() -> None:
    output = _run_benchmark('--repo', str(_TEST_REPO))
    report = json.loads(output)
    coverage = report['coverage_pct']
    assert isinstance(coverage, (int, float))
    assert 0.0 <= coverage <= 100.0, f'coverage_pct out of range: {coverage}'
    accuracy = report['accuracy_pct']
    assert isinstance(accuracy, (int, float))
    assert 0.0 <= accuracy <= 100.0, f'accuracy_pct out of range: {accuracy}'


def test_all_repo_map_symbols_are_mapped() -> None:
    output = _run_benchmark('--repo', str(_TEST_REPO))
    report = json.loads(output)
    missing = report.get('missing_symbols', [])
    assert len(missing) == 0, (
        f'Expected all __all__ symbols to be mapped, missing: {missing}'
    )


def test_parse_errors_is_empty() -> None:
    output = _run_benchmark('--repo', str(_TEST_REPO))
    report = json.loads(output)
    assert report.get('parse_errors') == [], (
        f'Expected no parse errors, got: {report["parse_errors"]}'
    )


def test_output_file_writes_json(tmp_path: Path) -> None:
    out_file = tmp_path / 'report.json'
    result = subprocess.run(
        [
            sys.executable, str(_SCRIPT),
            '--repo', str(_TEST_REPO),
            '--output', str(out_file),
        ],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f'stderr: {result.stderr}'
    assert out_file.exists()
    content = out_file.read_text(encoding='utf-8')
    report = json.loads(content)
    assert 'coverage_pct' in report


def test_pretty_flag_produces_readable_json() -> None:
    output = _run_benchmark('--repo', str(_TEST_REPO), '--pretty')
    lines = output.split('\n')
    assert len(lines) > 1, 'Pretty output should be multi-line'
    report = json.loads(output)
    assert 'coverage_pct' in report


def test_missing_repo_reports_error() -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), '--repo', '/nonexistent/path'],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode != 0
