from __future__ import annotations

from pathlib import Path

from teaagent.skill_candidate_artifacts import write_candidate_artifacts
from teaagent.skill_candidates import SkillCandidateStore
from teaagent.skill_eval import load_eval_report, run_offline_eval


def test_offline_eval_passes_valid_bundle(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    write_candidate_artifacts(
        candidate_dir,
        name='eval-skill',
        description='offline eval coverage',
        source_run_id='run-1',
        task='Write tests first for every change in the repository.',
        final_answer='Always run pytest before committing and document failures.',
        created_at='2026-05-24T00:00:00+00:00',
        content_digest='abc123',
    )
    (candidate_dir / 'SKILL.md').write_text(
        '---\nname: eval-skill\ndescription: test\n---\n\n# Instructions\nDo the thing.\n',
        encoding='utf-8',
    )
    report = run_offline_eval(candidate_dir)
    assert report.passed
    assert not report.failures


def test_offline_eval_fails_oversized_skill(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    write_candidate_artifacts(
        candidate_dir,
        name='big',
        description='too big',
        source_run_id='run-2',
        task='x' * 100,
        final_answer='y' * 100,
        created_at='2026-05-24T00:00:00+00:00',
    )
    (candidate_dir / 'SKILL.md').write_text('x' * 40_000, encoding='utf-8')
    report = run_offline_eval(candidate_dir, max_skill_bytes=1000)
    assert not report.passed
    assert any('exceeds max size' in item for item in report.failures)


def test_create_from_run_writes_eval_report(tmp_path: Path) -> None:
    runs_dir = tmp_path / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True)
    run_id = 'run-eval'
    events = [
        {
            'run_id': run_id,
            'event_type': 'run_started',
            'payload': {'task': 'Document testing workflow'},
        },
        {
            'run_id': run_id,
            'event_type': 'run_completed',
            'payload': {'answer': 'Use pytest and keep tests small.'},
        },
    ]
    import json

    (runs_dir / f'{run_id}.jsonl').write_text(
        '\n'.join(json.dumps(event) for event in events) + '\n',
        encoding='utf-8',
    )
    row = SkillCandidateStore(tmp_path).create_from_run(
        run_id=run_id,
        name='from-run',
        description='candidate from completed run',
    )
    report = load_eval_report(
        SkillCandidateStore(tmp_path).candidate_dir(row.candidate_id)
    )
    assert report is not None
    assert report.passed
    assert row.status == 'proposed'
