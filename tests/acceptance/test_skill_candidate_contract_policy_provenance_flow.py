"""Agent-created skill: candidate bundle must include contract/policy/provenance artifacts."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.skill_candidate_artifacts import (
    REQUIRED_CANDIDATE_ARTIFACTS,
    write_candidate_artifacts,
)


def _propose_candidate(tmp_path: Path) -> str:
    run_out = io.StringIO()
    with (
        patch(
            'teaagent.cli.create_llm_adapter',
            return_value=FakeAdapter(
                ['{"type":"final","content":"Write tests before implementation."}']
            ),
        ),
        redirect_stdout(run_out),
    ):
        assert (
            main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'testing workflow',
                    '--root',
                    str(tmp_path),
                    '--permission-mode',
                    'read-only',
                ]
            )
            == 0
        )
    run_id = json.loads(run_out.getvalue())['run_id']
    propose_out = io.StringIO()
    with redirect_stdout(propose_out):
        assert (
            main(
                [
                    'skill',
                    'candidate',
                    'propose',
                    '--root',
                    str(tmp_path),
                    '--from-run',
                    run_id,
                    '--name',
                    'test-first',
                    '--description',
                    'Test-first workflow',
                ]
            )
            == 0
        )
    return json.loads(propose_out.getvalue())['candidate']['candidate_id']


def test_skill_candidate_contract_policy_provenance_flow(tmp_path: Path) -> None:
    candidate_id = _propose_candidate(tmp_path)
    candidate_dir = tmp_path / '.teaagent' / 'skill-candidates' / candidate_id
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        assert (candidate_dir / name).is_file(), name

    (candidate_dir / 'provenance.json').unlink()

    review_out = io.StringIO()
    with redirect_stdout(review_out):
        review_code = main(
            [
                'skill',
                'candidate',
                'review',
                candidate_id,
                '--root',
                str(tmp_path),
            ]
        )
    assert review_code == 0
    reviewed = json.loads(review_out.getvalue())
    assert reviewed['status'] == 'review_failed'

    write_candidate_artifacts(
        candidate_dir,
        name='test-first',
        description='Test-first workflow',
        source_run_id='run-repair',
        task='testing workflow',
        final_answer='Write tests before implementation.',
        created_at='2026-05-24T00:00:00Z',
    )

    review_out = io.StringIO()
    with redirect_stdout(review_out):
        assert (
            main(
                [
                    'skill',
                    'candidate',
                    'review',
                    candidate_id,
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    assert json.loads(review_out.getvalue())['status'] == 'review_passed'

    (candidate_dir / 'SKILL.md').write_text(
        '---\nname: test-first\ndescription: Test-first workflow\n---\n\n'
        '# Context\n- Source task: testing workflow\n\n'
        '# Instructions\nChanged after review.\n',
        encoding='utf-8',
    )
    install_out = io.StringIO()
    with redirect_stdout(install_out):
        tampered_code = main(
            [
                'skill',
                'candidate',
                'install',
                candidate_id,
                '--scope',
                'project',
                '--root',
                str(tmp_path),
            ]
        )
    assert tampered_code == 1
    assert 'content_digest' in install_out.getvalue()

    (candidate_dir / 'SKILL.md').write_text(
        '---\nname: test-first\ndescription: Test-first workflow\n---\n\n'
        '# Context\n- Source task: testing workflow\n\n'
        '# Instructions\nWrite tests before implementation.\n',
        encoding='utf-8',
    )
    (candidate_dir / 'interaction_policy.json').unlink()
    install_out = io.StringIO()
    with redirect_stdout(install_out):
        blocked_code = main(
            [
                'skill',
                'candidate',
                'install',
                candidate_id,
                '--scope',
                'project',
                '--root',
                str(tmp_path),
            ]
        )
    assert blocked_code == 1
    assert 'interaction_policy.json' in install_out.getvalue()

    write_candidate_artifacts(
        candidate_dir,
        name='test-first',
        description='Test-first workflow',
        source_run_id='run-repair',
        task='testing workflow',
        final_answer='Write tests before implementation.',
        created_at='2026-05-24T00:00:00Z',
    )

    install_out = io.StringIO()
    with redirect_stdout(install_out):
        assert (
            main(
                [
                    'skill',
                    'candidate',
                    'install',
                    candidate_id,
                    '--scope',
                    'project',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    skill_dir = tmp_path / '.config' / 'agent' / 'skills' / 'test-first'
    assert (skill_dir / 'SKILL.md').exists()
    assert (skill_dir / 'REFERENCE.md').exists()
    assert (skill_dir / 'provenance.json').exists()
