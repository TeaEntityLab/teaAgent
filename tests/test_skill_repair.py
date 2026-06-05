from __future__ import annotations

import json
from pathlib import Path

from teaagent.skill_candidates import SkillCandidateStore
from teaagent.skill_eval import EvalReport, EvalRunResult
from teaagent.skill_repair import (
    RepairTask,
    generate_repair_tasks,
    load_repair_tasks,
    repair_tasks_path,
    write_repair_tasks,
)


def test_repair_task_dataclass() -> None:
    task = RepairTask(
        area='artifact',
        description='Create a SKILL.md file',
        severity='error',
        eval_failure='missing SKILL.md',
    )
    d = task.to_dict()
    assert d['area'] == 'artifact'
    assert d['description'] == 'Create a SKILL.md file'
    assert d['severity'] == 'error'
    assert d['eval_failure'] == 'missing SKILL.md'

    restored = RepairTask.from_dict(d)
    assert restored.area == task.area
    assert restored.description == task.description
    assert restored.severity == task.severity
    assert restored.eval_failure == task.eval_failure


def test_generate_repair_tasks_from_failures() -> None:
    report = EvalReport(
        candidate_name='test-candidate',
        passed=False,
        results=[],
        summary={},
        created_at='2026-06-05T00:00:00+00:00',
        checks=(),
        failures=('missing SKILL.md', 'missing REFERENCE.md'),
        content_digest='',
    )
    tasks = generate_repair_tasks(report, Path('/tmp'))
    assert len(tasks) >= 2
    areas = {t.area for t in tasks}
    assert 'artifact' in areas


def test_generate_repair_tasks_behavioral_failures() -> None:
    results = [
        EvalRunResult(
            case_name='markdown_check',
            passed=False,
            failures=[
                'missing expected title: "Report"',
                'row count mismatch: expected 3, got 2',
            ],
            output='bad output',
        ),
        EvalRunResult(
            case_name='json_check',
            passed=True,
            failures=[],
            output='{"ok": true}',
        ),
    ]
    report = EvalReport(
        candidate_name='test',
        passed=False,
        results=results,
        summary={},
        created_at='2026-06-05T00:00:00+00:00',
        checks=(),
        failures=(
            'missing expected title: "Report"',
            'row count mismatch: expected 3, got 2',
        ),
        content_digest='',
    )
    tasks = generate_repair_tasks(report, Path('/tmp'))
    behavioral = [t for t in tasks if t.area == 'fixture_validation']
    assert len(behavioral) == 1
    assert 'markdown_check' in behavioral[0].description
    assert 'json_check' not in behavioral[0].description


def test_generate_repair_tasks_no_failures() -> None:
    report = EvalReport(
        candidate_name='test',
        passed=True,
        results=[],
        summary={},
        created_at='2026-06-05T00:00:00+00:00',
        checks=(),
        failures=(),
        content_digest='abc',
    )
    tasks = generate_repair_tasks(report, Path('/tmp'))
    assert tasks == []


def test_write_and_load_repair_tasks(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()
    tasks = [
        RepairTask(
            area='artifact',
            description='Create a SKILL.md file',
            severity='error',
            eval_failure='missing SKILL.md',
        ),
        RepairTask(
            area='content',
            description='Expand REFERENCE.md',
            severity='warning',
            eval_failure='REFERENCE.md too short for offline eval',
        ),
    ]
    path = write_repair_tasks(candidate_dir, tasks)
    assert path == repair_tasks_path(candidate_dir)
    assert path.is_file()

    loaded = load_repair_tasks(candidate_dir)
    assert len(loaded) == 2
    assert loaded[0].area == tasks[0].area
    assert loaded[0].description == tasks[0].description
    assert loaded[0].severity == tasks[0].severity
    assert loaded[0].eval_failure == tasks[0].eval_failure
    assert loaded[1].area == tasks[1].area


def test_create_from_run_generates_repair_tasks_on_eval_failure(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True)
    run_id = 'run-repair-fail'
    huge_answer = 'x' * 40_000
    events = [
        {
            'run_id': run_id,
            'event_type': 'run_started',
            'payload': {'task': 'Document testing workflow'},
        },
        {
            'run_id': run_id,
            'event_type': 'run_completed',
            'payload': {'answer': huge_answer},
        },
    ]
    (runs_dir / f'{run_id}.jsonl').write_text(
        '\n'.join(json.dumps(event) for event in events) + '\n',
        encoding='utf-8',
    )
    row = SkillCandidateStore(tmp_path).create_from_run(
        run_id=run_id,
        name='fail-candidate',
        description='should fail eval from oversized skill',
    )
    assert row.status == 'eval_failed'

    candidate_dir = SkillCandidateStore(tmp_path).candidate_dir(row.candidate_id)
    tasks = load_repair_tasks(candidate_dir)
    assert len(tasks) >= 1
    areas = {t.area for t in tasks}
    assert 'size' in areas


def test_create_from_run_no_repair_tasks_on_success(tmp_path: Path) -> None:
    runs_dir = tmp_path / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True)
    run_id = 'run-repair-success'
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
    (runs_dir / f'{run_id}.jsonl').write_text(
        '\n'.join(json.dumps(event) for event in events) + '\n',
        encoding='utf-8',
    )
    row = SkillCandidateStore(tmp_path).create_from_run(
        run_id=run_id,
        name='success-candidate',
        description='should pass eval',
    )
    assert row.status == 'proposed'

    candidate_dir = SkillCandidateStore(tmp_path).candidate_dir(row.candidate_id)
    assert not repair_tasks_path(candidate_dir).is_file()
