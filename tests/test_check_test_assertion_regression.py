# test-type: behavior
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


def _fake_git(messages: dict[str, str], parents: str):
    """Fake ``_git``: ``log -1`` per ref, and a ``rev-list --parents`` line for HEAD."""

    def fake(args: list[str]) -> tuple[int, str]:
        if args[:2] == ['rev-list', '--parents']:
            return 0, parents
        if args[:2] == ['log', '-1']:
            ref = args[-1] if len(args) > 3 else 'HEAD'
            return (0, messages[ref]) if ref in messages else (128, '')
        return 128, ''

    return fake


def test_override_read_from_pr_head_of_a_merge_ref(monkeypatch) -> None:
    """On pull_request CI, HEAD is GitHub's merge commit; the trailer is on HEAD^2."""
    monkeypatch.delenv('ALLOW_TEST_WEAKENING', raising=False)
    monkeypatch.setattr(
        _mod,
        '_git',
        _fake_git(
            {
                'HEAD': 'Merge abc into def',
                'HEAD^2': 'x\n\nAllow-test-weakening: moved',
            },
            'merge base pr',
        ),
    )
    assert _mod._override_active() == 'commit trailer: moved'


def test_override_not_taken_from_second_parent_of_a_plain_commit(monkeypatch) -> None:
    monkeypatch.delenv('ALLOW_TEST_WEAKENING', raising=False)
    monkeypatch.setattr(
        _mod,
        '_git',
        _fake_git(
            {'HEAD': 'fix: plain', 'HEAD^2': 'Allow-test-weakening: ignored'},
            'head parent',
        ),
    )
    assert _mod._override_active() is None
