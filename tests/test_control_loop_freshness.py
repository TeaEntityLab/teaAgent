from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / 'scripts'
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_control_loop_freshness import main as validator_main  # noqa: E402


def test_all_roadmap_rows_have_ids() -> None:
    """Run the validator on the actual roadmap file and assert it passes."""
    roadmap = _REPO_ROOT / 'docs' / 'roadmap-status.md'
    assert roadmap.is_file(), f'Roadmap file not found: {roadmap}'
    result = validator_main(['--check-file', str(roadmap)])
    assert result == 0, (
        'Validator failed on the actual roadmap. '
        'All control-loop section rows must have IDs and status markers.'
    )


def test_validator_detects_missing_id(tmp_path: Path) -> None:
    """A control-loop section row without a control-loop ID should fail."""
    md = tmp_path / 'test_missing_id.md'
    md.write_text(
        '\n'.join(
            [
                '## Cross-Horizon Track - Seven Control Loops',
                '',
                '| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |',
                '|-----|-----------|-------|--------|------------|-----------|------|',
                '| BAD-001 | Missing control-loop ID | TBD | Proposed | Medium | NEXT-001 | High |',
                '',
            ]
        )
    )
    result = validator_main(['--check-file', str(md)])
    assert result == 1, 'Validator should fail when a row lacks a control-loop ID.'


def test_validator_detects_missing_status(tmp_path: Path) -> None:
    """A control-loop section row with an ID but no status marker should fail."""
    md = tmp_path / 'test_missing_status.md'
    md.write_text(
        '\n'.join(
            [
                '## Cross-Horizon Track - Seven Control Loops',
                '',
                '| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |',
                '|-----|-----------|-------|--------|------------|-----------|------|',
                '| SCL-P0-001 | Has ID but no status | TBD | ?????? | Medium | NEXT-001 | High |',
                '',
            ]
        )
    )
    result = validator_main(['--check-file', str(md)])
    assert result == 1, 'Validator should fail when a row lacks a status marker.'


def test_validator_passes_valid_file(tmp_path: Path) -> None:
    """A file with all proper control-loop rows should pass."""
    md = tmp_path / 'test_valid.md'
    md.write_text(
        '\n'.join(
            [
                '## Cross-Horizon Track - Seven Control Loops',
                '',
                '| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |',
                '|-----|-----------|-------|--------|------------|-----------|------|',
                '| SCL-P0-001 | Valid row | TBD | Proposed | Medium | NEXT-001 | High |',
                '| CPP-P1-003 | Another valid row | TBD | In Progress | Low | NEXT-002 | Medium |',
                '| DSK-P2-001 | Third valid row | TBD | Complete | High | NEXT-003 | Low |',
                '',
                '## Non-control-loop section',
                '',
                '| ID | Work Item | Owner | Status |',
                '|-----|-----------|-------|--------|',
                '| OTHER-01 | Not checked | TBD | Pending |',
                '',
            ]
        )
    )
    result = validator_main(['--check-file', str(md)])
    assert result == 0, 'Validator should pass when all control-loop rows are valid.'
