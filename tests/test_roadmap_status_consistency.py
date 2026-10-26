from __future__ import annotations

# test-type: contract
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VALIDATE_SCRIPT = _ROOT / 'scripts' / 'validate_docs_consistency.py'

_VALIDATE_SPEC = spec_from_file_location('validate_docs_consistency', _VALIDATE_SCRIPT)
assert _VALIDATE_SPEC and _VALIDATE_SPEC.loader
_VALIDATE_MODULE = module_from_spec(_VALIDATE_SPEC)
_VALIDATE_SPEC.loader.exec_module(_VALIDATE_MODULE)
check_roadmap_backlog_status = _VALIDATE_MODULE.check_roadmap_backlog_status

_ROADMAP_HEADER = (
    '| ID | Work Item | Implementation Status | Scheduling | Confidence |\n'
    '|----|-----------|-----------------------|------------|------------|\n'
)
_BACKLOG_HEADER = '| Item | Tag | Scheduling |\n| --- | --- | --- |\n'


def _roadmap(*rows: str) -> str:
    return '# Roadmap\n\n' + _ROADMAP_HEADER + ''.join(f'{row}\n' for row in rows)


def _backlog(*rows: str) -> str:
    return '# Backlog\n\n' + _BACKLOG_HEADER + ''.join(f'{row}\n' for row in rows)


def test_consistent_roadmap_and_backlog_produce_no_errors() -> None:
    roadmap = _roadmap(
        '| EFX-001 | Refuse blind redispatch | In Progress — runner sandwich | Promote | High |',
        '| VND-002 | Insider-threat class | Complete — added to threat model | Promote | High |',
    )
    backlog = _backlog(
        '| EFX-001 | Refuse blind redispatch | `governance-gap` | **In progress (2026-08-25)** — runner |',
        '| VND-002 | Insider-threat class | `governance-gap` | **Done (2026-09-14)** — added |',
    )

    assert check_roadmap_backlog_status(roadmap, backlog) == []


def test_done_versus_in_progress_reports_one_error_naming_both_lines() -> None:
    roadmap = _roadmap(
        '| EFX-001 | Refuse blind redispatch | In Progress — runner | Promote | High |',
    )
    backlog = _backlog(
        '| EFX-001 | Refuse blind redispatch | `governance-gap` | **Done (2026-09-13)** — shipped |',
    )

    errors = check_roadmap_backlog_status(
        roadmap,
        backlog,
        roadmap_label='roadmap.md',
        backlog_label='backlog.md',
    )

    assert len(errors) == 1
    assert 'EFX-001' in errors[0]
    assert 'roadmap.md:' in errors[0]
    assert 'backlog.md:' in errors[0]
    assert 'active' in errors[0] and 'done' in errors[0]


def test_unparseable_status_is_ignored() -> None:
    # Roadmap "Absent" and "TBD" are outside the vocabulary, so no bucket is
    # confidently parsed and the mismatch with backlog "Done" must not fire.
    roadmap = _roadmap(
        '| EFX-001 | Refuse blind redispatch | Absent | TBD | High |',
        '| EFX-002 | Fail closed | TBD | TBD | High |',
    )
    backlog = _backlog(
        '| EFX-001 | Refuse blind redispatch | `governance-gap` | **Done (2026-09-13)** |',
        '| EFX-002 | Fail closed | `governance-gap` | **Hold** — later |',
    )

    assert check_roadmap_backlog_status(roadmap, backlog) == []


def test_range_id_does_not_crash_and_is_skipped() -> None:
    roadmap = _roadmap(
        '| EFX-001..003 | Governance-gap cluster | Complete | Promote | High |',
        '| VND-001 | Live monitor lane | On Hold — later | Promote | High |',
    )
    backlog = _backlog(
        '| EFX-001 | Refuse blind redispatch | `governance-gap` | **In progress** |',
        '| VND-001 | Live monitor lane | `governance-gap` | **Done (2026-09-14)** |',
    )

    errors = check_roadmap_backlog_status(roadmap, backlog)

    assert len(errors) == 1
    assert 'VND-001' in errors[0]
    assert 'EFX-001' not in ' '.join(errors)


def test_check_runs_against_repo_docs_and_returns_a_list() -> None:
    roadmap = (_ROOT / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    backlog = (_ROOT / 'docs' / 'backlog-priority.md').read_text(encoding='utf-8')

    errors = check_roadmap_backlog_status(roadmap, backlog)

    assert isinstance(errors, list)
    assert all(isinstance(error, str) for error in errors)
