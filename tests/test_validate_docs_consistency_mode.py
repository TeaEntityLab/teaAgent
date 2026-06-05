"""Tests for test quality mode behavior in validate_docs_consistency."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add scripts directory to path for import
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from validate_docs_consistency import validate_test_quality


def test_validate_test_quality_off_mode():
    """Test that off mode skips audit entirely."""
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / 'tests'
        tests_dir.mkdir()

        errors = validate_test_quality(tests_dir, mode='off')

        assert errors == []


def test_validate_test_quality_report_mode_does_not_fail():
    """Test that report mode prints findings but does not fail validation."""
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / 'tests'
        tests_dir.mkdir()

        # Create a test file with no assertions
        test_file = tests_dir / 'test_weak.py'
        test_file.write_text('def test_weak():\n    pass\n', encoding='utf-8')

        errors = validate_test_quality(tests_dir, mode='report')

        # Report mode should not add errors
        assert errors == []


def test_validate_test_quality_report_mode_fails_on_collection_error():
    """Test that report mode still fails when pytest cannot collect tests."""
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / 'tests'
        tests_dir.mkdir()
        test_file = tests_dir / 'test_import_broken.py'
        test_file.write_text('import definitely_missing_module\n', encoding='utf-8')

        errors = validate_test_quality(tests_dir, mode='report')

        assert len(errors) == 1
        assert 'pytest collection failed' in errors[0]


def test_validate_test_quality_strict_mode_fails():
    """Test that strict mode adds errors for weak tests."""
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / 'tests'
        tests_dir.mkdir()

        # Create a test file with no assertions
        test_file = tests_dir / 'test_weak.py'
        test_file.write_text('def test_weak():\n    pass\n', encoding='utf-8')

        errors = validate_test_quality(tests_dir, mode='strict')

        # Strict mode should add errors
        assert len(errors) > 0
        assert any('no assertions' in err for err in errors)


def test_validate_test_quality_security_path_strict_mode():
    """Test that strict mode flags security/audit paths with no assertions."""
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / 'tests'
        tests_dir.mkdir()

        # Create a security test file with no assertions
        security_dir = tests_dir / 'security'
        security_dir.mkdir()
        test_file = security_dir / 'test_security.py'
        test_file.write_text('def test_security_weak():\n    pass\n', encoding='utf-8')

        errors = validate_test_quality(tests_dir, mode='strict')

        # Should flag security path
        assert len(errors) > 0
        assert any('security' in err for err in errors)
