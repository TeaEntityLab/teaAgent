from __future__ import annotations

import json
from pathlib import Path

from teaagent.skill_candidate_artifacts import write_candidate_artifacts
from teaagent.skill_eval import run_offline_eval
from teaagent.skill_eval_dataset import (
    run_eval_dataset_checks,
    write_default_eval_dataset,
)


def _write_bundle(candidate_dir: Path) -> None:
    write_candidate_artifacts(
        candidate_dir,
        name='eval-ds',
        description='dataset checks',
        source_run_id='run-1',
        task='Write pytest workflow instructions for the repository.',
        final_answer='Always run pytest before committing and document failures clearly.',
        created_at='2026-05-24T00:00:00+00:00',
    )
    (candidate_dir / 'SKILL.md').write_text(
        '---\nname: eval-ds\ndescription: dataset checks\n---\n\n# Instructions\n'
        'Always run pytest before committing.\n',
        encoding='utf-8',
    )


def test_default_eval_dataset_passes(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    _write_bundle(candidate_dir)
    write_default_eval_dataset(
        candidate_dir,
        task='Write pytest workflow instructions for the repository.',
        final_answer='Always run pytest before committing and document failures clearly.',
        skill_name='eval-ds',
    )
    checks, failures = run_eval_dataset_checks(candidate_dir)
    assert checks
    assert not failures
    report = run_offline_eval(candidate_dir)
    assert report.passed


def test_eval_dataset_custom_case_failure(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    _write_bundle(candidate_dir)
    (candidate_dir / 'eval_dataset.json').write_text(
        json.dumps(
            {
                'schema_version': 1,
                'cases': [
                    {
                        'id': 'must_mention_missing',
                        'check': 'skill_md_contains',
                        'substring': 'this-string-is-not-in-skill',
                    }
                ],
            }
        )
        + '\n',
        encoding='utf-8',
    )
    _, failures = run_eval_dataset_checks(candidate_dir)
    assert failures
    assert any('must_mention_missing' in item for item in failures)
