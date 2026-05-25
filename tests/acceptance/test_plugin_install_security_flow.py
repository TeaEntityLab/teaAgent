"""Skill install path enforces artifact contract, review gate, and attestation."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.skill_candidate_artifacts import (
    REQUIRED_CANDIDATE_ARTIFACTS,
    candidate_bundle_digest,
    validate_candidate_artifacts,
    write_candidate_artifacts,
)
from teaagent.skill_eval_dataset import write_default_eval_dataset
from teaagent.storage import atomic_write_text


def _seed_candidate(tmp_path: Path, candidate_id: str = 'plugin-sec') -> Path:
    candidate_dir = tmp_path / '.teaagent' / 'skill-candidates' / candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    (candidate_dir / 'SKILL.md').write_text(
        '---\nname: plugin-sec\ndescription: Security acceptance skill\n---\n\n# Safe install\n',
        encoding='utf-8',
    )
    write_candidate_artifacts(
        candidate_dir,
        name='plugin-sec',
        description='Security acceptance skill',
        source_run_id='run-plugin-sec',
        task='Document safe plugin install checks for the repository.',
        final_answer='Validate provenance before install.',
        created_at='2026-05-25T00:00:00+00:00',
    )
    write_default_eval_dataset(
        candidate_dir,
        task='Document safe plugin install checks for the repository.',
        final_answer='Validate provenance before install.',
        skill_name='plugin-sec',
    )
    digest = candidate_bundle_digest(candidate_dir)
    atomic_write_text(
        candidate_dir / 'provenance.json',
        json.dumps(
            {
                'schema_version': 1,
                'source_run_id': 'run-plugin-sec',
                'source_kind': 'agent_run',
                'source_task': 'Document safe plugin install checks for the repository.',
                'created_at': '2026-05-25T00:00:00+00:00',
                'content_digest': digest,
                'gate_content_digest': '',
                'trust_level': 'quarantine',
            },
            indent=2,
        )
        + '\n',
    )
    atomic_write_text(
        candidate_dir / 'candidate.json',
        json.dumps(
            {
                'candidate_id': candidate_id,
                'name': 'plugin-sec',
                'description': 'Security acceptance skill',
                'status': 'proposed',
                'created_at': '2026-05-25T00:00:00+00:00',
                'updated_at': '2026-05-25T00:00:00+00:00',
                'source_run_id': 'run-plugin-sec',
            }
        )
        + '\n',
    )
    return candidate_dir


def test_candidate_artifacts_required_before_install(tmp_path: Path) -> None:
    candidate_dir = _seed_candidate(tmp_path)
    assert validate_candidate_artifacts(candidate_dir) == []
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        assert (candidate_dir / name).is_file(), name

    (candidate_dir / 'provenance.json').unlink()
    errors = validate_candidate_artifacts(candidate_dir)
    assert errors
    assert any('provenance' in err.lower() for err in errors)

    review_out = io.StringIO()
    with redirect_stdout(review_out):
        review_code = main(
            [
                'skill',
                'candidate',
                'review',
                'plugin-sec',
                '--root',
                str(tmp_path),
            ]
        )
    assert review_code == 0
    reviewed = json.loads(review_out.getvalue())
    assert reviewed['status'] in {'review_failed', 'eval_failed'}

    _seed_candidate(tmp_path)
    eval_out = io.StringIO()
    with redirect_stdout(eval_out):
        eval_code = main(
            [
                'skill',
                'candidate',
                'eval',
                'plugin-sec',
                '--root',
                str(tmp_path),
            ]
        )
    eval_payload = json.loads(eval_out.getvalue())
    assert eval_code in (0, 2)
    assert 'eval' in eval_payload
