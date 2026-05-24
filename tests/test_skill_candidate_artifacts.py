from __future__ import annotations

import json
from pathlib import Path

from teaagent.skill_candidate_artifacts import (
    REQUIRED_CANDIDATE_ARTIFACTS,
    validate_candidate_artifacts,
    write_candidate_artifacts,
)


def test_write_and_validate_candidate_bundle(tmp_path: Path) -> None:
    (tmp_path / 'SKILL.md').write_text(
        '---\nname: demo\ndescription: Demo skill\n---\n',
        encoding='utf-8',
    )
    write_candidate_artifacts(
        tmp_path,
        name='demo',
        description='Demo skill',
        source_run_id='run-1',
        task='Do the thing',
        final_answer='Step one then step two.',
        created_at='2026-05-24T00:00:00Z',
    )
    assert validate_candidate_artifacts(tmp_path) == []
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        assert (tmp_path / name).is_file()
    provenance = json.loads((tmp_path / 'provenance.json').read_text(encoding='utf-8'))
    assert provenance['source_run_id'] == 'run-1'
    assert provenance['content_digest'].startswith('sha256:')


def test_validate_reports_missing_artifacts(tmp_path: Path) -> None:
    (tmp_path / 'SKILL.md').write_text('---\nname: x\n---\n', encoding='utf-8')
    errors = validate_candidate_artifacts(tmp_path)
    assert any('REFERENCE.md' in item for item in errors)


def test_validate_reports_invalid_json(tmp_path: Path) -> None:
    write_candidate_artifacts(
        tmp_path,
        name='demo',
        description='Demo',
        source_run_id='run-1',
        task='t',
        final_answer='a',
        created_at='2026-05-24T00:00:00Z',
    )
    (tmp_path / 'cost_profile.json').write_text('{not json', encoding='utf-8')
    errors = validate_candidate_artifacts(tmp_path)
    assert any('cost_profile.json' in item for item in errors)
