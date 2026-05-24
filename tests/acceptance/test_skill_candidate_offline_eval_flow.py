"""Offline eval gates skill candidates before review/install."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


def test_skill_candidate_offline_eval_flow(tmp_path: Path) -> None:
    run_out = io.StringIO()
    with (
        patch(
            'teaagent.cli.create_llm_adapter',
            return_value=FakeAdapter(
                ['{"type":"final","content":"Always run pytest before committing."}']
            ),
        ),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'agent',
                'run',
                'gpt',
                'Write concise Python testing workflow instructions',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
            ]
        )
    assert run_code == 0
    run_id = json.loads(run_out.getvalue())['run_id']

    propose_out = io.StringIO()
    with redirect_stdout(propose_out):
        propose_code = main(
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
                'pytest workflow from run',
            ]
        )
    assert propose_code == 0
    propose_payload = json.loads(propose_out.getvalue())
    assert propose_payload['status'] == 'proposed'
    assert propose_payload['eval']['passed'] is True
    candidate_id = propose_payload['candidate']['candidate_id']

    eval_out = io.StringIO()
    with redirect_stdout(eval_out):
        eval_code = main(
            [
                'skill',
                'candidate',
                'eval',
                candidate_id,
                '--root',
                str(tmp_path),
            ]
        )
    assert eval_code == 0
    assert json.loads(eval_out.getvalue())['status'] == 'eval_passed'
