"""Tests for the A1 test-assertion-regression gate (scripts/check_test_assertion_regression.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    'check_test_assertion_regression',
    Path(__file__).resolve().parents[1]
    / 'scripts'
    / 'check_test_assertion_regression.py',
)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _mod  # let dataclass resolve annotations against the module
_SPEC.loader.exec_module(_mod)

count_assertions_by_function = _mod.count_assertions_by_function
find_regressions = _mod.find_regressions


def test_counts_plain_asserts_and_unittest_and_pytest() -> None:
    src = """
import pytest

def test_plain():
    assert 1 == 1
    assert 2 == 2

class TestX:
    def test_method(self):
        self.assertEqual(1, 1)
        self.assertTrue(True)
        with pytest.raises(ValueError):
            raise ValueError

def helper_not_a_test():
    assert False
"""
    counts = count_assertions_by_function(src)
    assert counts == {'test_plain': 2, 'TestX.test_method': 3}
    assert 'helper_not_a_test' not in counts


def test_no_regression_when_assertions_added() -> None:
    base = 'def test_a():\n    assert 1\n'
    head = 'def test_a():\n    assert 1\n    assert 2\n'
    assert find_regressions('tests/x.py', base, head) == []


def test_flags_weakened_test() -> None:
    base = 'def test_a():\n    assert 1\n    assert 2\n'
    head = 'def test_a():\n    assert 1\n'
    regs = find_regressions('tests/x.py', base, head)
    assert len(regs) == 1
    assert regs[0].kind == 'weakened'
    assert regs[0].base_count == 2
    assert regs[0].head_count == 1


def test_flags_deleted_test() -> None:
    base = 'def test_a():\n    assert 1\n\ndef test_b():\n    assert 1\n'
    head = 'def test_a():\n    assert 1\n'
    regs = find_regressions('tests/x.py', base, head)
    assert len(regs) == 1
    assert regs[0].function == 'test_b'
    assert regs[0].kind == 'deleted'


def test_flags_whole_file_deletion() -> None:
    base = 'def test_a():\n    assert 1\n'
    regs = find_regressions('tests/x.py', base, head_src=None)
    assert len(regs) == 1
    assert regs[0].kind == 'deleted'


def test_new_file_is_not_a_regression() -> None:
    # A brand-new test file has no base; the caller skips it, but find_regressions
    # with an empty base must also be clean.
    head = 'def test_new():\n    assert 1\n'
    assert find_regressions('tests/x.py', '', head) == []


def test_assertionless_test_is_ignored() -> None:
    # A test with zero assertions can't "regress" — audit_test_quality.py owns that signal.
    base = 'def test_a():\n    x = 1\n'
    head = 'def test_a():\n    pass\n'
    assert find_regressions('tests/x.py', base, head) == []


def test_rename_within_file_flags_old_name() -> None:
    # Conservative by design: a rename reads as delete+add. Use the override for real renames.
    base = 'def test_old():\n    assert 1\n'
    head = 'def test_new():\n    assert 1\n'
    regs = find_regressions('tests/x.py', base, head)
    assert [r.function for r in regs] == ['test_old']
