"""Phase B: the check-high-risk-paths gate (review-system.md §4.2 / G4).

High-risk path changes (scripts/high_risk_paths.yaml) must be accompanied by a
reflective-risk report or an explicit acknowledgement.
"""

from __future__ import annotations

from scripts.check_high_risk_paths import (
    has_risk_report,
    high_risk_files,
    load_patterns,
    path_matches,
)


def test_patterns_load_from_yaml() -> None:
    patterns = load_patterns()
    assert patterns, 'high_risk_paths.yaml must define patterns'
    # Core security surfaces are covered.
    assert 'teaagent/policy.py' in patterns
    assert 'teaagent/runner/_core.py' in patterns


def test_glob_and_prefix_matching() -> None:
    assert path_matches('teaagent/approval_manager.py', 'teaagent/approval_*.py')
    assert path_matches('teaagent/audit_chain.py', 'teaagent/audit*.py')
    # Directory-prefix patterns match any file beneath.
    assert path_matches('teaagent/sandbox/_git_branch.py', 'teaagent/sandbox/')
    assert path_matches('teaagent/approval/manager.py', 'teaagent/approval/')
    # Non-matches.
    assert not path_matches('teaagent/cli/__init__.py', 'teaagent/policy.py')
    assert not path_matches('teaagent/subagents/_x.py', 'teaagent/sandbox/')


def test_high_risk_files_detection() -> None:
    patterns = load_patterns()
    assert high_risk_files(['teaagent/policy.py', 'README.md'], patterns) == [
        'teaagent/policy.py'
    ]
    assert high_risk_files(['scripts/foo.py', 'tests/test_x.py'], patterns) == []


def test_risk_report_satisfies_gate() -> None:
    assert has_risk_report(['docs/reviews/42-risk.md'])
    assert has_risk_report(['teaagent/policy.py', 'docs/reviews/abc-risk.md'])
    # A non-risk doc does not satisfy the gate.
    assert not has_risk_report(['docs/reviews/notes.md', 'teaagent/policy.py'])
