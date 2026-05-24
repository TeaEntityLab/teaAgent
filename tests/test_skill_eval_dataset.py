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
    (candidate_dir / 'SKILL.md').write_text(
        '---\nname: eval-ds\ndescription: dataset checks\n---\n\n# Instructions\n'
        'Always run pytest before committing.\n',
        encoding='utf-8',
    )
    write_candidate_artifacts(
        candidate_dir,
        name='eval-ds',
        description='dataset checks',
        source_run_id='run-1',
        task='Write pytest workflow instructions for the repository.',
        final_answer='Always run pytest before committing and document failures clearly.',
        created_at='2026-05-24T00:00:00+00:00',
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


def test_eval_dataset_all_check_types(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    _write_bundle(candidate_dir)
    (candidate_dir / 'eval_dataset.json').write_text(
        json.dumps(
            {
                'schema_version': 1,
                'cases': [
                    {
                        'id': 'task_len',
                        'check': 'source_task_min_length',
                        'min_length': 5,
                    },
                    {
                        'id': 'task_has',
                        'check': 'source_task_contains',
                        'substring': 'pytest',
                    },
                    {
                        'id': 'skill_has',
                        'check': 'skill_md_contains',
                        'substring': 'Instructions',
                    },
                    {
                        'id': 'skill_not',
                        'check': 'skill_md_not_contains',
                        'substring': 'ZZZNOTFOUNDZZZ',
                    },
                    {
                        'id': 'ref_has',
                        'check': 'reference_contains',
                        'substring': 'pytest',
                    },
                    {
                        'id': 'regex_ok',
                        'check': 'regex',
                        'target': 'skill_md',
                        'pattern': '^---',
                    },
                ],
            }
        )
        + '\n',
        encoding='utf-8',
    )
    checks, failures = run_eval_dataset_checks(candidate_dir)
    assert len(checks) == 6
    assert not failures


def test_eval_dataset_invalid_cases_array(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    (candidate_dir / 'eval_dataset.json').write_text(
        '{"schema_version": 1, "cases": "bad"}\n', encoding='utf-8'
    )
    checks, failures = run_eval_dataset_checks(candidate_dir)
    assert checks == ['eval_dataset']
    assert failures


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


def test_eval_dataset_unknown_check_and_bad_case(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    (candidate_dir / 'eval_dataset.json').write_text(
        json.dumps(
            {
                'schema_version': 1,
                'cases': [
                    'not-an-object',
                    {'id': 'unknown', 'check': 'nope'},
                    {
                        'id': 'regex_fail',
                        'check': 'regex',
                        'pattern': '^ZZZ',
                    },
                ],
            }
        )
        + '\n',
        encoding='utf-8',
    )
    (candidate_dir / 'SKILL.md').write_text('# skill\n', encoding='utf-8')
    checks, failures = run_eval_dataset_checks(candidate_dir)
    assert len(checks) >= 2
    assert failures


def test_load_eval_dataset_invalid_json(tmp_path: Path) -> None:
    from teaagent.skill_eval_dataset import load_eval_dataset

    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    (candidate_dir / 'eval_dataset.json').write_text('not json', encoding='utf-8')
    assert load_eval_dataset(candidate_dir) is None
