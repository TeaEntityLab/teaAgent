"""Tests for the test quality audit tool."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add scripts directory to path for import
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from audit_test_quality import collect_pytest_nodes, discover_test_files, scan_test_file


def test_scan_test_file_detects_placeholder():
    """Test that audit tool detects placeholder tests with no assertions."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_placeholder.py'
        test_file.write_text('def test_coming_soon():\n    pass\n', encoding='utf-8')

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert 'test_coming_soon' in metrics.weak_patterns
        assert 'no_assertions' in metrics.weak_patterns['test_coming_soon']


def test_scan_test_file_detects_assert_true():
    """Test that audit tool detects assert True."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_assert_true.py'
        test_file.write_text('def test_weak():\n    assert True\n', encoding='utf-8')

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert 'test_weak' in metrics.weak_patterns
        assert 'assert_true' in metrics.weak_patterns['test_weak']


def test_scan_test_file_detects_mock_only():
    """Test that audit tool detects mock-only tests."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_mock_only.py'
        test_file.write_text(
            'from unittest.mock import Mock\n\ndef test_mock_only():\n    mock_obj = Mock()\n    mock_obj.method()\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert 'test_mock_only' in metrics.weak_patterns
        assert 'mock_only' in metrics.weak_patterns['test_mock_only']


def test_scan_test_file_counts_assertions():
    """Test that audit tool correctly counts assertions."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_assertions.py'
        test_file.write_text(
            'def test_multiple_asserts():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert metrics.assertion_counts['test_multiple_asserts'] == 3
        assert 'test_multiple_asserts' not in metrics.weak_patterns


def test_scan_test_file_detects_docstrings():
    """Test that audit tool extracts docstrings."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_docstring.py'
        test_file.write_text(
            'def test_with_docstring():\n    """This test has a docstring."""\n    assert True\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert 'test_with_docstring' in metrics.docstrings
        assert metrics.docstrings['test_with_docstring'] == 'This test has a docstring.'


def test_scan_test_file_handles_syntax_error():
    """Test that audit tool handles syntax errors gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_syntax_error.py'
        test_file.write_text(
            'def test_broken(\n    # Missing closing paren\n', encoding='utf-8'
        )

        metrics = scan_test_file(test_file)

        assert metrics.has_syntax_error is True
        assert len(metrics.test_functions) == 0


def test_scan_test_file_counts_mocks():
    """Test that audit tool counts mock usage."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_mocks.py'
        test_file.write_text(
            'from unittest.mock import Mock, MagicMock, patch\n\ndef test_with_mocks():\n    m1 = Mock()\n    m2 = MagicMock()\n    with patch("some.module"): pass\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert metrics.mock_counts['test_with_mocks'] == 3


def test_scan_test_file_ignores_non_test_functions():
    """Test that audit tool only scans test functions."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_mixed.py'
        test_file.write_text(
            'def helper_function():\n    pass\n\ndef test_real_test():\n    assert True\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert 'test_real_test' in metrics.test_functions
        assert 'helper_function' not in metrics.test_functions


def test_scan_test_file_counts_unittest_assertions():
    """Test that audit tool counts unittest assertion methods."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_unittest.py'
        test_file.write_text(
            'import unittest\n\nclass TestExample(unittest.TestCase):\n    def test_example(self):\n        self.assertEqual(1, 1)\n        self.assertTrue(True)\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert metrics.assertion_counts['test_example'] == 2
        assert 'test_example' not in metrics.weak_patterns


def test_scan_test_file_counts_class_based_tests():
    """Test that audit tool correctly counts class-based test methods."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_class_based.py'
        test_file.write_text(
            'import unittest\n\nclass TestAudit(unittest.TestCase):\n    def test_event_has_fields(self):\n        self.assertTrue(True)\n\n    def test_event_id_unique(self):\n        self.assertTrue(False)\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 2
        assert 'test_event_has_fields' in metrics.test_functions
        assert 'test_event_id_unique' in metrics.test_functions
        assert metrics.assertion_counts['test_event_has_fields'] == 1
        assert metrics.assertion_counts['test_event_id_unique'] == 1


def test_scan_test_file_counts_async_tests():
    """Test that audit tool counts async test functions."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_async.py'
        test_file.write_text(
            'import pytest\n\nasync def test_async_example():\n    assert True\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert len(metrics.test_functions) == 1
        assert 'test_async_example' in metrics.test_functions


def test_discover_test_files_accepts_single_file_path():
    """Test that single-file audits still run AST quality checks."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_single_file.py'
        test_file.write_text('def test_single():\n    assert True\n', encoding='utf-8')

        assert discover_test_files(test_file) == [test_file]


def test_scan_test_file_detects_construction_only_tests():
    """Test that construction-only assertions are classified as weak."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_construction_only.py'
        test_file.write_text(
            'def test_constructs_object():\n'
            '    value = object()\n'
            '    assert isinstance(value, object)\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert 'test_constructs_object' in metrics.weak_patterns
        assert 'construction_only' in metrics.weak_patterns['test_constructs_object']


def test_scan_test_file_detects_none_and_type_construction_assertions():
    """Test common construction-only assert forms are classified."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_construction_forms.py'
        test_file.write_text(
            'def test_not_none_only():\n'
            '    value = object()\n'
            '    assert value is not None\n\n'
            'def test_type_only():\n'
            '    value = "x"\n'
            '    assert type(value) == str\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert 'construction_only' in metrics.weak_patterns['test_not_none_only']
        assert 'construction_only' in metrics.weak_patterns['test_type_only']


def test_scan_test_file_detects_undocumented_skip():
    """Test that skipped tests need an explicit skip reason."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_skip.py'
        test_file.write_text(
            'import pytest\n\n'
            '@pytest.mark.skip\n'
            'def test_skip_without_reason():\n'
            '    assert 1 == 1\n\n'
            '@pytest.mark.skip(reason="needs optional service")\n'
            'def test_skip_with_reason():\n'
            '    assert 1 == 1\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert 'undocumented_skip' in metrics.weak_patterns['test_skip_without_reason']
        assert 'test_skip_with_reason' not in metrics.weak_patterns


def test_scan_test_file_counts_pytest_raises_as_assertion():
    """Test that exception-boundary tests are not misclassified as empty."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_pytest_raises.py'
        test_file.write_text(
            'import pytest\n\n'
            'def test_rejects_bad_value():\n'
            '    with pytest.raises(ValueError, match="bad"):\n'
            '        raise ValueError("bad")\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert metrics.assertion_counts['test_rejects_bad_value'] == 1
        assert 'test_rejects_bad_value' not in metrics.weak_patterns


def test_collect_pytest_nodes_keeps_class_based_node_ids():
    """Test collection preserves class-based node IDs instead of truncating them."""
    with tempfile.TemporaryDirectory() as tmp:
        tests_dir = Path(tmp) / 'tests'
        tests_dir.mkdir()
        test_file = tests_dir / 'test_class_nodes.py'
        test_file.write_text(
            'class TestNodeCollection:\n'
            '    def test_inside_class(self):\n'
            '        assert True\n',
            encoding='utf-8',
        )

        nodes = collect_pytest_nodes(tests_dir)

        assert any(
            node.endswith('::TestNodeCollection::test_inside_class') for node in nodes
        )


def test_collect_pytest_nodes_raises_on_failure():
    """Test that collect_pytest_nodes raises RuntimeError on pytest failure."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create an invalid test directory
        invalid_dir = Path(tmp) / 'invalid_tests'
        invalid_dir.mkdir()

        try:
            collect_pytest_nodes(invalid_dir)
            raise AssertionError('Expected RuntimeError to be raised')
        except RuntimeError as e:
            assert 'pytest collection failed' in str(e)


def test_classify_test_type_path_heuristic_acceptance():
    """Test that files under tests/acceptance/ are classified as behavior."""
    from audit_test_quality import classify_test_type

    # Create a fake path under tests/acceptance/
    test_path = Path('/repo/tests/acceptance/test_some_flow.py')
    test_type = classify_test_type(test_path)
    assert test_type == 'behavior'


def test_classify_test_type_path_heuristic_lifecycle():
    """Test that files under tests/lifecycle/ are classified as lifecycle."""
    from audit_test_quality import classify_test_type

    test_path = Path('/repo/tests/lifecycle/test_event_sequence.py')
    test_type = classify_test_type(test_path)
    assert test_type == 'lifecycle'


def test_classify_test_type_path_heuristic_adversarial():
    """Test that files with 'adversarial' in name are classified as adversarial."""
    from audit_test_quality import classify_test_type

    test_path = Path('/repo/tests/test_adversarial_boundary.py')
    test_type = classify_test_type(test_path)
    assert test_type == 'adversarial'


def test_classify_test_type_default_contract():
    """Test that other files default to contract type."""
    from audit_test_quality import classify_test_type

    test_path = Path('/repo/tests/test_some_unit.py')
    test_type = classify_test_type(test_path)
    assert test_type == 'contract'


def test_classify_test_type_explicit_pytestmark_override():
    """Test that explicit pytestmark = pytest.mark.test_type() overrides path heuristic."""
    from audit_test_quality import classify_test_type

    # Even though path says "acceptance" (behavior), explicit marker says "contract"
    source = "pytestmark = pytest.mark.test_type('contract')\n\ndef test_something():\n    assert True\n"
    test_path = Path('/repo/tests/acceptance/test_override.py')
    test_type = classify_test_type(test_path, source)
    assert test_type == 'contract'


def test_classify_test_type_explicit_comment_override():
    """Test that explicit # test-type: comment overrides path heuristic."""
    from audit_test_quality import classify_test_type

    source = '# test-type: lifecycle\n\ndef test_something():\n    assert True\n'
    test_path = Path('/repo/tests/test_some_flow.py')
    test_type = classify_test_type(test_path, source)
    assert test_type == 'lifecycle'


def test_classify_test_type_precedence_pytestmark_over_comment():
    """Test that pytestmark takes precedence over comment."""
    from audit_test_quality import classify_test_type

    source = (
        "pytestmark = pytest.mark.test_type('behavior')\n"
        '# test-type: contract\n'
        '\ndef test_something():\n    assert True\n'
    )
    test_path = Path('/repo/tests/test_flow.py')
    test_type = classify_test_type(test_path, source)
    assert test_type == 'behavior'


def test_scan_test_file_includes_test_type():
    """Test that scan_test_file populates test_type field."""
    with tempfile.TemporaryDirectory() as tmp:
        acceptance_dir = Path(tmp) / 'acceptance'
        acceptance_dir.mkdir()
        test_file = acceptance_dir / 'test_flow.py'
        test_file.write_text(
            'def test_user_flow():\n    assert True\n', encoding='utf-8'
        )

        metrics = scan_test_file(test_file)

        assert metrics.test_type == 'behavior'


def test_scan_test_file_with_explicit_test_type_marker():
    """Test that explicit marker is respected during scanning."""
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / 'test_explicit.py'
        test_file.write_text(
            "pytestmark = pytest.mark.test_type('adversarial')\n\n"
            'def test_rejects_bad_input():\n    assert True\n',
            encoding='utf-8',
        )

        metrics = scan_test_file(test_file)

        assert metrics.test_type == 'adversarial'
