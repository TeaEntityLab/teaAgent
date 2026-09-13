# test-type: contract
"""Tests for scripts/validate_evidence_ledger.py.

The 2026-09-12 agentflow-structures panel found the delivery evidence-ledger
had zero code consumers and already held a self-contradictory entry
(recheck_date + date_checked unknown) that nothing flagged. These tests pin
the validator's contract: honest entries pass, each known-bad shape fails.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_evidence_ledger import main, validate_entry, validate_ledger


def _good_entry() -> dict[str, str]:
    return {
        'claim': 'smoke tier green',
        'source': 'run_test_tier.py --tier smoke (read 2026-09-12)',
        'attester': 'deterministic script gate (exit 0)',
        'freshness_kind': 'recheck_date',
        'date_checked': '2026-09-12',
    }


def test_valid_recheck_entry_passes() -> None:
    assert validate_entry(_good_entry(), origin='t', index=0) == []


def test_valid_pinned_entry_passes() -> None:
    entry = _good_entry()
    entry.update(
        {'freshness_kind': 'immutable_pin', 'pinned_commit': 'abc1234'},
    )
    assert validate_entry(entry, origin='t', index=0) == []


def test_recheck_with_unknown_date_fails() -> None:
    entry = _good_entry()
    entry['date_checked'] = 'unknown'
    errors = validate_entry(entry, origin='t', index=3)
    assert any('date_checked' in error for error in errors)


def test_pin_without_anchor_fails() -> None:
    entry = _good_entry()
    entry['freshness_kind'] = 'immutable_pin'
    errors = validate_entry(entry, origin='t', index=0)
    assert any('pinned_commit' in error for error in errors)


def test_unknown_attester_fails() -> None:
    entry = _good_entry()
    entry['attester'] = 'unknown'
    errors = validate_entry(entry, origin='t', index=0)
    assert any('attester' in error for error in errors)


def test_bad_freshness_kind_fails() -> None:
    entry = _good_entry()
    entry['freshness_kind'] = 'vibes'
    errors = validate_entry(entry, origin='t', index=0)
    assert any('freshness_kind' in error for error in errors)


def test_missing_keys_fail() -> None:
    errors = validate_entry({'claim': 'x'}, origin='t', index=0)
    assert any('missing required keys' in error for error in errors)


def test_ledger_file_honest_passes_and_dishonest_fails(tmp_path: Path) -> None:
    good = tmp_path / 'good.yaml'
    good.write_text(
        'entries:\n'
        '  - claim: c\n'
        '    source: s\n'
        '    attester: read tool\n'
        '    freshness_kind: recheck_date\n'
        '    date_checked: "2026-09-12"\n',
        encoding='utf-8',
    )
    assert validate_ledger(good) == []
    assert main(['--ledger', str(good)]) == 0

    bad = tmp_path / 'bad.yaml'
    bad.write_text(
        'entries:\n'
        '  - claim: carried suite\n'
        '    source: prior session\n'
        '    attester: unknown\n'
        '    freshness_kind: recheck_date\n'
        '    date_checked: unknown\n',
        encoding='utf-8',
    )
    assert validate_ledger(bad)
    assert main(['--ledger', str(bad)]) == 1


def test_real_delivery_ledger_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    ledgers = sorted(root.glob('.teaagent/delivery/*/evidence-ledger.yaml'))
    assert ledgers, 'expected at least one delivery evidence ledger'
    errors: list[str] = []
    for ledger in ledgers:
        errors.extend(validate_ledger(ledger))
    assert errors == []
