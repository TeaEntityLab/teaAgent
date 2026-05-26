"""AC: run --from-plan binds execution to a plan artifact and audit provenance."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.plan import load_plan_contract
from teaagent.run_store import RunStore


def test_run_from_plan_records_provenance(tmp_path: Path) -> None:
    (tmp_path / '.teaagent').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.teaagent' / 'config.toml').write_text(
        'provider = "gpt"\n', encoding='utf-8'
    )

    plan_out = io.StringIO()
    with redirect_stdout(plan_out):
        plan_code = main(
            [
                'plan',
                'gpt',
                'Bind execution to this reviewed plan',
                '--root',
                str(tmp_path),
            ]
        )
    plan_payload = json.loads(plan_out.getvalue())
    assert plan_code in (0, 2)
    artifact = Path(plan_payload['plan_artifact'])
    contract = load_plan_contract(artifact, root=tmp_path)

    adapter = FakeAdapter(
        ['{"type":"final","content":"plan-bound run complete"}'],
    )
    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'run',
                'gpt',
                '--from-plan',
                str(artifact.relative_to(tmp_path)),
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
                '--max-iterations',
                '3',
            ]
        )
    run_payload = json.loads(run_out.getvalue())
    assert run_code == 0
    assert run_payload['plan_contract']['content_hash'] == contract.content_hash
    assert run_payload['plan_contract']['task'] == contract.task

    events = RunStore(tmp_path).show_run(run_payload['run_id'])
    started = next(e for e in events if e.get('event_type') == 'run_started')
    assert started['payload']['plan_path'] == contract.rel_path
    assert started['payload']['plan_content_hash'] == contract.content_hash
    assert started['payload']['task'] == contract.task
