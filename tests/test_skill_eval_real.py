from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from teaagent.skill_eval import EvalReport, EvalRunResult
from teaagent.skill_eval_real import (
    load_real_eval_report,
    real_eval_report_path,
    write_real_eval_report,
)


def test_real_eval_report_path() -> None:
    candidate_dir = Path('/tmp/test-candidate')
    assert (
        real_eval_report_path(candidate_dir) == candidate_dir / 'eval_report_real.json'
    )


def test_write_and_load_real_eval_report(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'cand'
    candidate_dir.mkdir()

    report = EvalReport(
        candidate_name='test-candidate',
        passed=True,
        results=[
            EvalRunResult(
                case_name='markdown_titles_check',
                passed=True,
                failures=[],
                output='# Quarterly Report\n\n## Revenue\n- Q1: $10M\n',
            ),
        ],
        summary={
            'total_cases': 1,
            'passed_cases': 1,
            'failed_cases': 0,
            'model': 'gpt-4o',
            'provider': 'gpt',
        },
        created_at='2026-06-05T00:00:00+00:00',
        checks=('real_model_eval',),
        failures=(),
        content_digest='',
    )

    written_path = write_real_eval_report(candidate_dir, report)
    assert written_path == candidate_dir / 'eval_report_real.json'
    assert written_path.is_file()

    loaded = load_real_eval_report(candidate_dir)
    assert loaded is not None
    assert loaded.candidate_name == 'test-candidate'
    assert loaded.passed is True
    assert loaded.summary['total_cases'] == 1
    assert loaded.summary['model'] == 'gpt-4o'
    assert loaded.summary['provider'] == 'gpt'
    assert len(loaded.results) == 1
    assert loaded.results[0].case_name == 'markdown_titles_check'


def test_real_eval_cli_parser_registered() -> None:
    from teaagent.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['skill', 'candidate', 'eval-real', '--help'])

    args = parser.parse_args(
        [
            'skill',
            'candidate',
            'eval-real',
            'candidate-abc',
            '--model',
            'gpt-4o',
            '--provider',
            'gpt',
            '--root',
            '/tmp/test-root',
        ]
    )
    assert args.skill_command == 'candidate'
    assert args.skill_candidate_command == 'eval-real'
    assert args.candidate_id == 'candidate-abc'
    assert args.model == 'gpt-4o'
    assert args.provider == 'gpt'
    assert args.root == '/tmp/test-root'
    assert args.func is not None


def test_load_real_eval_report_nonexistent(tmp_path: Path) -> None:
    candidate_dir = tmp_path / 'nonexistent'
    report = load_real_eval_report(candidate_dir)
    assert report is None


def test_real_eval_candidate_not_found(tmp_path: Path) -> None:
    from teaagent.cli._handlers._skill import skill_candidate_eval_real_command

    (tmp_path / '.teaagent' / 'skill-candidates').mkdir(parents=True)

    args = argparse.Namespace(
        candidate_id='nonexistent-candidate',
        model='gpt-4o',
        provider='gpt',
        root=str(tmp_path),
    )
    result = skill_candidate_eval_real_command(args)
    assert result == 1
