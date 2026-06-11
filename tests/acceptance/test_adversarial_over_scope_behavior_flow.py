"""AC: adversarial over-scope behavior is blocked and surfaced in receipts.

Acceptance criteria:
- Unauthorized workspace writes are stopped with a pending approval result.
- Unauthorized shell mutation is stopped with a pending approval result.
- A run cannot claim completion without verification evidence.
- A plan-bounded run cannot expand scope beyond the approved file targets.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.evidence_summary import build_evidence_summary
from teaagent.plan import load_plan_contract
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.run_evidence import build_run_evidence_bundle, check_evidence_completeness
from teaagent.run_store import RunStore
from teaagent.runner._plan_validator import PlanValidator
from teaagent.types import AuditLogger


def _run_agent(
    tmp_path: Path,
    task: str,
    responses: list[str],
    *,
    permission_mode: str,
    extra_args: list[str] | None = None,
) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    adapter = FakeAdapter(responses)
    args = [
        'agent',
        'run',
        'gpt',
        task,
        '--root',
        str(tmp_path),
        '--permission-mode',
        permission_mode,
    ]
    if extra_args:
        args.extend(extra_args)
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(output),
    ):
        exit_code = main(args)
    return exit_code, json.loads(output.getvalue())


def test_adversarial_unauthorized_workspace_write_is_blocked(tmp_path: Path) -> None:
    exit_code, payload = _run_agent(
        tmp_path,
        'Update a file without write approval',
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"notes.txt","content":"changed"},"call_id":"write-1"}'
        ],
        permission_mode='read-only',
    )

    assert exit_code == 1
    assert payload['status'] == 'pending_approval'
    assert payload['approval']['reason_code'] == 'read_only_mode'
    assert payload['tool_calls'] == 0


def test_adversarial_unauthorized_shell_mutation_is_blocked(
    tmp_path: Path,
) -> None:
    exit_code, payload = _run_agent(
        tmp_path,
        'Run a shell mutation without approval',
        [
            '{"type":"tool","tool_name":"workspace_run_shell_mutate","arguments":{"command":"rm -rf tmp","timeout_seconds":3},"call_id":"shell-1"}'
        ],
        permission_mode='read-only',
    )

    assert exit_code == 1
    assert payload['status'] == 'pending_approval'
    assert payload['approval']['reason_code'] == 'read_only_mode'
    assert payload['tool_calls'] == 0


def test_adversarial_completion_without_verification_is_flagged(
    tmp_path: Path,
) -> None:
    run_id = 'run-missing-verification'
    store = RunStore(tmp_path)
    audit = AuditLogger(path=store.run_path(run_id))
    audit.record('run_started', run_id, task='ship a change', model='gpt')
    audit.record(
        'tool_use',
        run_id,
        tool_name='workspace_write_file',
        input={'path': 'README.md', 'content': 'updated'},
    )
    audit.record('run_completed', run_id, answer='done', total_cost=0.01)

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    summary = build_evidence_summary(store, run_id, tmp_path)
    missing = check_evidence_completeness(
        bundle,
        store.show_run(run_id),
        summary.status,
    )

    assert summary.status == 'success'
    assert summary.tests_executed == 0
    assert 'empty list field: tests' in missing


def test_adversarial_plan_scope_expansion_is_blocked(tmp_path: Path) -> None:
    plans_dir = tmp_path / '.teaagent' / 'plans'
    plans_dir.mkdir(parents=True, exist_ok=True)
    artifact = plans_dir / 'tight-scope.md'
    artifact.write_text(
        '\n'.join(
            [
                '# Tight scope',
                '',
                '## Summary',
                '- **Task:** Update the approved docs file only.',
                '',
                '## Files likely touched',
                '- `docs/allowed.md`',
            ]
        ),
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    assert contract.file_targets == frozenset({'docs/allowed.md'})

    validator = PlanValidator(
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE),
        require_plan=True,
    )
    validator.set_plan_contract(contract)
    context = {'plan_contract': contract.to_dict()}

    allowed = validator.validate_write_allowed(
        tool_name='workspace_write_file',
        context=context,
        tool_arguments={
            'path': 'docs/allowed.md',
            'content': 'updated',
        },
    )
    blocked = validator.validate_write_allowed(
        tool_name='workspace_write_file',
        context=context,
        tool_arguments={
            'path': 'docs/disallowed.md',
            'content': 'expanded',
        },
    )

    assert allowed is None
    assert blocked is not None
    assert 'outside the approved plan scope' in blocked
