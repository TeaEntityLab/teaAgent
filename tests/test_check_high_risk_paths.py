"""Phase B: the check-high-risk-paths gate (review-system.md §4.2 / G4).

High-risk path changes (scripts/high_risk_paths.yaml) must be accompanied by a
reflective-risk report or an explicit acknowledgement.
"""

from __future__ import annotations

from scripts.check_high_risk_paths import (
    ack_references_existing_report,
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


def test_ack_with_existing_report_reference_passes() -> None:
    assert ack_references_existing_report(
        'ref docs/reviews/efx-001-003-durable-effect-risk.md: perf reorder'
    )


def test_ack_without_report_reference_fails() -> None:
    assert not ack_references_existing_report('trivial reorder only')
    assert not ack_references_existing_report('')


def test_ack_citing_missing_report_fails() -> None:
    assert not ack_references_existing_report(
        'ref docs/reviews/nonexistent-risk.md: stale ref'
    )


def test_main_rejects_ack_without_report_reference(monkeypatch, capsys) -> None:
    from scripts import check_high_risk_paths as gate

    monkeypatch.setattr(gate, 'load_patterns', lambda: ['teaagent/policy.py'])
    monkeypatch.setattr(gate, '_staged_files', lambda: ['teaagent/policy.py'])
    monkeypatch.setenv('TEAAGENT_RISK_ACK', 'trivial reorder only')
    assert gate.main() == 1
    assert 'must cite an existing risk report' in capsys.readouterr().out


def test_main_accepts_ack_with_existing_report_reference(monkeypatch, capsys) -> None:
    from scripts import check_high_risk_paths as gate

    monkeypatch.setattr(gate, 'load_patterns', lambda: ['teaagent/policy.py'])
    monkeypatch.setattr(gate, '_staged_files', lambda: ['teaagent/policy.py'])
    monkeypatch.setenv(
        'TEAAGENT_RISK_ACK',
        'ref docs/reviews/efx-001-003-durable-effect-risk.md: follow-up',
    )
    assert gate.main() == 0
    assert 'high-risk paths acknowledged' in capsys.readouterr().out
