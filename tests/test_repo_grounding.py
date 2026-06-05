"""Tests for spec grounding — repository grounding check for spec-to-plan transitions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.goal_record import GoalRecord, GoalStore
from teaagent.spec_grounding import (
    GroundingCheck,
    SpecBinding,
    emit_spec_grounding_checked,
    emit_spec_promoted_to_plan,
    extract_file_refs,
    perform_grounding_check,
    persist_grounding,
)

# ── extract_file_refs ────────────────────────────────────────────────────


def test_extract_backtick_paths():
    text = 'See `src/main.py` and `tests/test_auth.ts`.'
    refs = extract_file_refs(text)
    assert 'src/main.py' in refs
    assert 'tests/test_auth.ts' in refs


def test_extract_markdown_links():
    text = '[config](.teaagent/config.json) and [README](README.md).'
    refs = extract_file_refs(text)
    assert '.teaagent/config.json' in refs
    assert 'README.md' in refs


def test_extract_plain_paths():
    text = 'Run from src/cli.py or docs/usage.md.'
    refs = extract_file_refs(text)
    assert 'src/cli.py' in refs
    assert 'docs/usage.md' in refs


def test_extract_ignores_urls():
    text = 'Download from https://example.com/file.tar.gz and see `README.md`.'
    refs = extract_file_refs(text)
    assert 'README.md' in refs
    for r in refs:
        assert not r.startswith('http')


def test_extract_ignores_version_numbers():
    text = 'Version 3.10.2 is required. See `setup.py`.'
    refs = extract_file_refs(text)
    assert 'setup.py' in refs
    assert '3.10.2' not in refs


def test_extract_ignores_emails():
    text = 'Contact dev@example.com. See `teaagent/plan.py`.'
    refs = extract_file_refs(text)
    assert 'teaagent/plan.py' in refs
    assert 'dev@example.com' not in refs


def test_extract_deduplicates():
    text = '`foo.py` and `foo.py` again.'
    refs = extract_file_refs(text)
    assert refs == ['foo.py']


def test_extract_empty():
    assert extract_file_refs('') == []
    assert extract_file_refs('No file references here.') == []


# ── perform_grounding_check ──────────────────────────────────────────────


def test_grounding_check_valid_files(monkeypatch, tmp_path: Path):
    """All referenced files exist → grounding_valid=True."""
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'main.py').write_text('print(1)')
    (tmp_path / 'README.md').write_text('# Project')

    spec = tmp_path / 'spec.md'
    spec.write_text('See `src/main.py` and `README.md`.')

    check = perform_grounding_check(spec, workspace_root=tmp_path, spec_id='spec-1')
    assert check.grounding_valid
    assert check.missing_files == []
    assert 'src/main.py' in check.files_searched
    assert 'README.md' in check.files_searched


def test_grounding_check_missing_files(tmp_path: Path):
    """Referenced file does not exist → grounding_valid=False."""
    spec = tmp_path / 'spec.md'
    spec.write_text('See `src/missing.py`.')

    check = perform_grounding_check(spec, workspace_root=tmp_path, spec_id='spec-2')
    assert not check.grounding_valid
    assert 'src/missing.py' in check.missing_files


def test_grounding_check_external_paths_are_ok(tmp_path: Path):
    """Paths outside workspace are not required to exist."""
    spec = tmp_path / 'spec.md'
    spec.write_text('See `/etc/hosts` and `README.md`.')
    (tmp_path / 'README.md').write_text('# hi')

    check = perform_grounding_check(spec, workspace_root=tmp_path, spec_id='spec-3')
    # /etc/hosts is external → not flagged as missing
    assert check.grounding_valid


def test_grounding_check_assumptions_confirmed():
    """All assumptions are confirmed when none are weak."""
    spec = Path('/nonexistent/spec.md')  # won't be read
    check = perform_grounding_check(
        spec,
        workspace_root=Path('/tmp'),
        spec_id='spec-4',
        assumptions=[
            'Planning is read-only.',
            'Provider gpt applies.',
        ],
    )
    assert check.grounding_valid
    assert 'Planning is read-only.' in check.assumptions_confirmed
    assert 'Provider gpt applies.' in check.assumptions_confirmed
    assert check.failed_assumptions == []


def test_grounding_check_weak_assumptions():
    """Assumptions indicating ambiguity are flagged as failed."""
    check = perform_grounding_check(
        Path('/nonexistent/spec.md'),
        workspace_root=Path('/tmp'),
        spec_id='spec-5',
        assumptions=[
            'Planning is read-only.',
            'Task ambiguity is above the clarify threshold; execution should wait.',
        ],
    )
    assert not check.grounding_valid
    assert 'Planning is read-only.' in check.assumptions_confirmed
    assert len(check.failed_assumptions) == 1
    assert 'ambiguity' in check.failed_assumptions[0].lower()


def test_grounding_check_candidate_files_merged(tmp_path: Path):
    """Pre-resolved candidate files are merged with extracted refs."""
    (tmp_path / 'a.py').write_text('')
    (tmp_path / 'b.py').write_text('')

    spec = tmp_path / 'spec.md'
    spec.write_text('See `c.py`.')
    (tmp_path / 'c.py').write_text('')

    check = perform_grounding_check(
        spec,
        workspace_root=tmp_path,
        spec_id='spec-6',
        candidate_files=['a.py', 'b.py'],
    )
    assert check.grounding_valid
    for f in ('a.py', 'b.py', 'c.py'):
        assert f in check.files_searched


def test_grounding_check_empty_spec(tmp_path: Path):
    """Empty or non-existent spec file still works."""
    spec = tmp_path / 'no_such.md'
    check = perform_grounding_check(spec, workspace_root=tmp_path, spec_id='spec-7')
    assert check.grounding_valid
    assert check.files_searched == []


# ── SpecBinding serialization ────────────────────────────────────────────


def test_spec_binding_to_dict_round_trip():
    binding = SpecBinding(
        spec_id='spec-a',
        spec_hash='sha256:aaa',
        plan_id='plan-b',
        plan_hash='sha256:bbb',
        searched_files=['src/a.py', 'tests/test_a.py'],
        confirmed_assumptions=['Planning is read-only.'],
        transitioned_at='2026-06-05T00:00:00Z',
    )
    data = binding.to_dict()
    restored = SpecBinding.from_dict(data)
    assert restored.spec_id == binding.spec_id
    assert restored.spec_hash == binding.spec_hash
    assert restored.plan_id == binding.plan_id
    assert restored.plan_hash == binding.plan_hash
    assert restored.searched_files == binding.searched_files
    assert restored.confirmed_assumptions == binding.confirmed_assumptions
    assert restored.transitioned_at == binding.transitioned_at


def test_spec_binding_defaults():
    binding = SpecBinding(
        spec_id='s', spec_hash='h', plan_id='p', plan_hash='h2'
    )
    assert binding.searched_files == []
    assert binding.confirmed_assumptions == []
    assert binding.transitioned_at  # auto-filled


# ── GroundingCheck serialization ─────────────────────────────────────────


def test_grounding_check_to_dict_round_trip():
    check = GroundingCheck(
        spec_id='spec-9',
        files_searched=['a.py', 'b.py'],
        assumptions_confirmed=['Assumption 1'],
        grounding_valid=False,
        missing_files=['b.py'],
        failed_assumptions=[],
    )
    data = check.to_dict()
    restored = GroundingCheck.from_dict(data)
    assert restored.spec_id == check.spec_id
    assert restored.files_searched == check.files_searched
    assert restored.assumptions_confirmed == check.assumptions_confirmed
    assert restored.grounding_valid == check.grounding_valid
    assert restored.missing_files == check.missing_files
    assert restored.failed_assumptions == check.failed_assumptions


def test_grounding_check_from_dict_partial():
    """Missing keys in from_dict get sensible defaults."""
    check = GroundingCheck.from_dict({'spec_id': 's'})
    assert check.spec_id == 's'
    assert check.files_searched == []
    assert check.assumptions_confirmed == []
    assert not check.grounding_valid


# ── audit events ─────────────────────────────────────────────────────────


def test_emit_spec_promoted_to_plan(tmp_path: Path):
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    binding = SpecBinding(
        spec_id='spec-e1',
        spec_hash='sha256:abc',
        plan_id='plan-e1',
        plan_hash='sha256:def',
        searched_files=['src/x.py'],
        confirmed_assumptions=['Read-only planning'],
        transitioned_at='2026-06-05T12:00:00Z',
    )
    emit_spec_promoted_to_plan(audit, binding)
    audit.record('_flush', 'spec')  # ensure disk write
    assert log_path.is_file()
    lines = log_path.read_text().strip().split('\n')
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert event['event_type'] == 'spec_promoted_to_plan'
    assert event['payload']['spec_id'] == 'spec-e1'
    assert event['payload']['searched_files'] == ['src/x.py']


def test_emit_spec_grounding_checked(tmp_path: Path):
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    check = GroundingCheck(
        spec_id='spec-ec',
        files_searched=['main.py'],
        assumptions_confirmed=['a1'],
        grounding_valid=True,
    )
    emit_spec_grounding_checked(audit, check)
    audit.record('_flush', 'spec')
    lines = log_path.read_text().strip().split('\n')
    event = json.loads(lines[0])
    assert event['event_type'] == 'spec_grounding_checked'
    assert event['payload']['grounding_valid'] is True
    assert event['payload']['files_searched'] == ['main.py']


# ── persist_grounding ────────────────────────────────────────────────────


def test_persist_grounding_writes_file():
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        check = GroundingCheck(
            spec_id='spec-p1',
            files_searched=['f1.py'],
            assumptions_confirmed=['a1'],
            grounding_valid=True,
        )
        path = persist_grounding(check, store)
        assert path.is_file()
        data = json.loads(path.read_text())
        assert data['grounding']['spec_id'] == 'spec-p1'
        assert data['grounding']['grounding_valid'] is True


def test_persist_grounding_with_binding():
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        check = GroundingCheck(
            spec_id='spec-p2',
            files_searched=['f.py'],
            assumptions_confirmed=['a'],
            grounding_valid=True,
        )
        binding = SpecBinding(
            spec_id='spec-p2',
            spec_hash='sha256:s',
            plan_id='plan-p2',
            plan_hash='sha256:p',
            searched_files=['f.py'],
            confirmed_assumptions=['a'],
        )
        path = persist_grounding(check, store, binding=binding)
        data = json.loads(path.read_text())
        assert 'binding' in data
        assert data['binding']['spec_id'] == 'spec-p2'
        assert data['binding']['plan_id'] == 'plan-p2'


def test_persist_grounding_appends_goal_audit():
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(
            goal_id='g-audit',
            objective='Test grounding audit',
            spec_id='spec-a1',
            status='proposed',
        )
        store.save(goal)

        check = GroundingCheck(
            spec_id='spec-a1',
            files_searched=['x.py'],
            assumptions_confirmed=['read-only ok'],
            grounding_valid=True,
        )
        binding = SpecBinding(
            spec_id='spec-a1',
            spec_hash='sha256:aa',
            plan_id='plan-aa',
            plan_hash='sha256:bb',
        )
        persist_grounding(check, store, binding=binding)

        audit_path = store._root / 'g-audit_audit.jsonl'
        assert audit_path.is_file()
        lines = audit_path.read_text().strip().split('\n')
        event_types = []
        for line in lines:
            entry = json.loads(line)
            event_types.append(entry['event_type'])
        assert 'spec_promoted_to_plan' in event_types
        assert 'spec_grounding_checked' in event_types


# ── edge cases ───────────────────────────────────────────────────────────


def test_perform_grounding_check_nonexistent_spec():
    """Non-existent spec path should not crash."""
    check = perform_grounding_check(
        Path('/nonexistent/spec.md'),
        workspace_root=Path('/tmp'),
        spec_id='spec-edge',
    )
    assert check.grounding_valid
    assert check.files_searched == []


def test_grounding_all_valid_with_no_missing_files(tmp_path: Path):
    """When all referenced files exist and no weak assumptions, valid=True."""
    (tmp_path / 'a.py').write_text('')
    (tmp_path / 'b.py').write_text('')
    spec = tmp_path / 'spec.md'
    spec.write_text('`a.py` `b.py`')
    check = perform_grounding_check(spec, workspace_root=tmp_path, spec_id='ok')
    assert check.grounding_valid
    assert check.missing_files == []
