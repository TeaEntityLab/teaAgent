"""Tests for scripts/validate_wiring.py."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from validate_wiring import (  # noqa: E402
    WATCH_MODULES,
    _has_unwired_label,
    analyze_wiring,
    validate_wiring,
)


def test_head_wiring_watch_modules_labeled() -> None:
    errors = validate_wiring()
    assert errors == []


def test_analyze_wiring_finds_unwired_watch_modules() -> None:
    report = analyze_wiring()
    assert report.unwired_watch
    assert 'teaagent.rbac' in report.unwired_watch
    assert 'teaagent.eval_suite' not in report.unwired_watch


def test_unlabeled_fixture_fails_validation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / 'teaagent'
        package.mkdir()
        island = package / 'rbac.py'
        island.write_text(
            '"""RBAC without label."""\n',
            encoding='utf-8',
        )
        (package / 'cli').mkdir()
        (package / 'cli' / '__init__.py').write_text('', encoding='utf-8')

        errors = validate_wiring(repo_root=root)
        assert any('teaagent.rbac' in error for error in errors)


def test_labeled_fixture_passes_validation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / 'teaagent'
        package.mkdir()
        island = package / 'rbac.py'
        island.write_text(
            '"""RBAC.\n\nexperimental — unwired\n"""\n',
            encoding='utf-8',
        )
        (package / 'cli').mkdir()
        (package / 'cli' / '__init__.py').write_text('', encoding='utf-8')

        errors = validate_wiring(repo_root=root)
        assert errors == []


def test_has_unwired_label_detects_banner() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'sample.py'
        path.write_text(
            '"""Title.\n\nexperimental — unwired\n"""\n',
            encoding='utf-8',
        )
        assert _has_unwired_label(path)


def test_watch_modules_include_h4_h5_h6_clusters() -> None:
    assert 'teaagent.policy_engine' in WATCH_MODULES
    assert 'teaagent.update.installer' in WATCH_MODULES
