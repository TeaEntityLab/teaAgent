from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from teaagent.cli._handlers._skill import skill_health_command
from teaagent.skill_loader import get_skill_health


def _install_skill(base: Path, rel_dir: str, name: str) -> Path:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: Skill {name}\n---\n# {name}\n\n## Content\n'
        f'Sample content for {name}. ' * 30,
        encoding='utf-8',
    )
    return skill_dir


def _add_candidate(
    base: Path,
    candidate_id: str,
    name: str,
    status: str,
    *,
    updated_at: str | None = None,
) -> Path:
    candidates_dir = base / '.teaagent' / 'skill-candidates'
    candidates_dir.mkdir(parents=True, exist_ok=True)
    cand_dir = candidates_dir / candidate_id
    cand_dir.mkdir(parents=True, exist_ok=True)
    (cand_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n# {name}\n',
        encoding='utf-8',
    )
    from teaagent.skill_candidates import SkillCandidate

    now = datetime.now(timezone.utc)
    if updated_at is None:
        updated_at = now.isoformat()

    candidate = SkillCandidate(
        candidate_id=candidate_id,
        name=name,
        description=f'{name} description',
        status=status,
        created_at=now.isoformat(),
        updated_at=updated_at,
    )
    (cand_dir / 'candidate.json').write_text(
        json.dumps(candidate.to_dict()), encoding='utf-8'
    )

    (cand_dir / 'provenance.json').write_text(
        json.dumps({'source_run_id': 'run_001', 'content_digest': 'abc123'}),
        encoding='utf-8',
    )
    (cand_dir / 'REFERENCE.md').write_text(
        '# Reference\n\nThis is a reference document with enough content for validation.',
        encoding='utf-8',
    )
    return cand_dir


def _add_eval_report(
    candidate_dir: Path,
    *,
    passed: bool = True,
    failures: list[str] | None = None,
) -> None:
    failures = failures or []
    report = {
        'candidate_name': candidate_dir.name,
        'passed': passed,
        'results': [],
        'summary': {
            'total_cases': 2,
            'passed_cases': 2 if passed else 0,
            'failed_cases': 0 if passed else 2,
        },
        'created_at': datetime.now(timezone.utc).isoformat(),
        'checks': ['required_artifacts', 'skill_size'],
        'failures': failures,
        'content_digest': 'abc123',
    }
    (candidate_dir / 'eval_report.json').write_text(
        json.dumps(report), encoding='utf-8'
    )


class TestSkillHealthEmptyWorkspace:
    def test_skill_health_empty_workspace(self, tmp_path: Path) -> None:
        health = get_skill_health(tmp_path)
        assert isinstance(health['total_skills'], int)
        assert health['loaded_skills_count'] == 0
        assert health['governance_distribution'] == {
            'direct_write': 0,
            'candidate_installed': 0,
            'compatibility_path': 0,
            'unmanaged': 0,
        }
        assert health['shadowed_count'] == 0
        assert health['candidate_summary']['total'] == 0
        assert health['stale_candidates'] == []
        assert health['failed_evals'] == []
        assert health['warnings'] == []
        assert health['skipped'] == []

    def test_skill_health_with_installed_skills(self, tmp_path: Path) -> None:
        _install_skill(tmp_path, '.config/agent/skills', 'alpha')
        _install_skill(tmp_path, '.config/agent/skills', 'beta')
        _install_skill(tmp_path, '.claude/skills', 'gamma')

        health = get_skill_health(tmp_path)
        assert health['loaded_skills_count'] >= 0
        gov = health['governance_distribution']
        assert gov['direct_write'] >= 0


class TestSkillHealthWithCandidates:
    def test_skill_health_with_candidates(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc)
        _add_candidate(tmp_path, 'c1', 'alpha', 'proposed', updated_at=now.isoformat())
        _add_candidate(
            tmp_path, 'c2', 'beta', 'eval_failed', updated_at=now.isoformat()
        )
        _add_candidate(
            tmp_path, 'c3', 'gamma', 'review_passed', updated_at=now.isoformat()
        )
        _add_candidate(tmp_path, 'c4', 'delta', 'installed', updated_at=now.isoformat())
        _add_candidate(
            tmp_path, 'c5', 'epsilon', 'review_failed', updated_at=now.isoformat()
        )

        _add_eval_report(
            tmp_path / '.teaagent' / 'skill-candidates' / 'c2',
            passed=False,
            failures=['Missing required field', 'SKILL.md too short'],
        )

        health = get_skill_health(tmp_path)
        cs = health['candidate_summary']
        assert cs['total'] == 5
        assert cs['proposed'] == 1
        assert cs['eval_failed'] == 1
        assert cs['review_passed'] == 1
        assert cs['installed'] == 1
        assert cs['review_failed'] == 1

        assert len(health['failed_evals']) == 1
        assert health['failed_evals'][0]['name'] == 'beta'
        assert len(health['failed_evals'][0]['failures']) == 2

        assert health['stale_candidates'] == []

    def test_skill_health_stale_detection(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc)
        eight_days_ago = (now - timedelta(days=8)).isoformat()
        six_days_ago = (now - timedelta(days=6)).isoformat()

        _add_candidate(
            tmp_path, 's1', 'stale_proposed', 'proposed', updated_at=eight_days_ago
        )
        _add_candidate(
            tmp_path, 's2', 'stale_failed', 'eval_failed', updated_at=eight_days_ago
        )
        _add_candidate(
            tmp_path, 's3', 'fresh_proposed', 'proposed', updated_at=six_days_ago
        )
        _add_candidate(
            tmp_path, 's4', 'installed_old', 'installed', updated_at=eight_days_ago
        )

        health = get_skill_health(tmp_path)
        assert len(health['stale_candidates']) == 2
        stale_names = {s['name'] for s in health['stale_candidates']}
        assert stale_names == {'stale_proposed', 'stale_failed'}

    def test_skill_health_candidate_with_eval_failures(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc)
        _add_candidate(
            tmp_path, 'c1', 'bad_skill', 'eval_failed', updated_at=now.isoformat()
        )
        _add_eval_report(
            tmp_path / '.teaagent' / 'skill-candidates' / 'c1',
            passed=False,
            failures=[
                'provenance.json missing content_digest',
                'REFERENCE.md too short',
            ],
        )

        health = get_skill_health(tmp_path)
        assert len(health['failed_evals']) == 1
        fe = health['failed_evals'][0]
        assert fe['name'] == 'bad_skill'
        assert fe['candidate_id'] == 'c1'
        assert 'provenance.json missing content_digest' in fe['failures']
        assert 'REFERENCE.md too short' in fe['failures']

    def test_skill_health_failed_eval_no_report_file(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc)
        _add_candidate(
            tmp_path, 'c1', 'no_report', 'eval_failed', updated_at=now.isoformat()
        )
        # Do NOT add eval_report.json — simulates missing report

        health = get_skill_health(tmp_path)
        assert len(health['failed_evals']) == 1
        assert health['failed_evals'][0]['failures'] == []


class TestCLISkillHealthCommand:
    def test_cli_skill_health_command_empty(self, tmp_path: Path, capsys) -> None:
        args = argparse.Namespace(root=str(tmp_path))
        result = skill_health_command(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output['total_skills'], int)
        assert output['candidate_summary']['total'] == 0

    def test_cli_skill_health_command_with_candidates(
        self, tmp_path: Path, capsys
    ) -> None:
        now = datetime.now(timezone.utc)
        _add_candidate(
            tmp_path, 'c1', 'alpha', 'review_passed', updated_at=now.isoformat()
        )
        _add_candidate(tmp_path, 'c2', 'beta', 'installed', updated_at=now.isoformat())

        args = argparse.Namespace(root=str(tmp_path))
        result = skill_health_command(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output['candidate_summary']['total'] == 2
        assert output['candidate_summary']['review_passed'] == 1
        assert output['candidate_summary']['installed'] == 1
