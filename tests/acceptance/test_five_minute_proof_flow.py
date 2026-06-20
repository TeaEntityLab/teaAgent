"""AC-W10: Five-minute governance proof flow.

End-to-end demonstration that TeaAgent's governance thesis holds:

  1. Plan validation  — no write proceeds without an approved plan.
  2. Approval         — every mutation is gated by an explicit approval record.
  3. File edit        — the agent edits exactly the file declared in the plan.
  4. Verification     — the agent confirms its fix before declaring done.
  5. Evidence receipt — budget/tool/file/approval receipts are emitted.
  6. Undo             — the workspace can be restored to the pre-run state.

Provider: fake (no API key required).

Follows the pattern established in test_first_hour_e2e_flow.py and
test_run_evidence_summary_flow.py.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.plan import load_plan_contract
from teaagent.run_receipt import build_run_receipt, check_receipt_completeness
from teaagent.run_store import RunStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BUGGY_SRC = 'def add(a, b):\n    return a - b\n'
_FIXED_SRC = 'def add(a, b):\n    return a + b\n'

_PLAN_MD = """\
# Plan

## Summary
- **Task:** Fix the bug in calc.py — subtraction operator should be addition

## Files likely touched
- `calc.py`
"""

_FAKE_RESPONSES = [
    # Step 2: agent requests to write the fix (triggers approval gate)
    json.dumps(
        {
            'type': 'tool',
            'tool_name': 'workspace_write_file',
            'arguments': {'path': 'calc.py', 'content': _FIXED_SRC},
            'call_id': 'fix-write',
        }
    ),
    # Step 4: agent verifies the fix via grep (grep is in the inspect-safe allowlist)
    json.dumps(
        {
            'type': 'tool',
            'tool_name': 'workspace_run_shell_inspect',
            'arguments': {'command': "grep -n 'return a' calc.py"},
            'call_id': 'verify-fix',
        }
    ),
    # Step 5: agent declares completion
    '{"type":"final","content":"calc.py fixed: subtraction corrected to addition; verification passed"}',
]

_GIT_ENV = {
    'GIT_AUTHOR_NAME': 'TeaAgent Proof',
    'GIT_AUTHOR_EMAIL': 'proof@teaagent.test',
    'GIT_COMMITTER_NAME': 'TeaAgent Proof',
    'GIT_COMMITTER_EMAIL': 'proof@teaagent.test',
}


def _setup_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (calc_path, plan_file_path) after writing all workspace files."""
    calc = tmp_path / 'calc.py'
    calc.write_text(_BUGGY_SRC, encoding='utf-8')

    (tmp_path / 'test_calc.py').write_text(
        'from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n',
        encoding='utf-8',
    )

    plans_dir = tmp_path / '.teaagent' / 'plans'
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / 'fix-calc.md'
    plan_file.write_text(_PLAN_MD, encoding='utf-8')

    return calc, plan_file


def _git_baseline(tmp_path: Path) -> bool:
    """Create a git baseline commit so git-sandbox rollback is available. Returns success."""
    env = {**os.environ, **_GIT_ENV}
    for cmd in (
        ['git', 'init'],
        ['git', 'add', 'calc.py', 'test_calc.py'],
        ['git', 'commit', '-m', 'baseline'],
    ):
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, env=env)
        if result.returncode != 0:
            return False
    return True


# ---------------------------------------------------------------------------
# Test 1: Plan gate enforcement
# ---------------------------------------------------------------------------


def test_proof_step1_plan_gate_blocks_write_without_plan(tmp_path: Path) -> None:
    """Plan gate must return exit-code 2 and leave the file untouched when
    --require-plan is set but no --from-plan is supplied."""
    calc, _ = _setup_workspace(tmp_path)

    # Adapter is created but .complete() is never called — gate fires first.
    adapter = FakeAdapter(
        [
            json.dumps(
                {
                    'type': 'tool',
                    'tool_name': 'workspace_write_file',
                    'arguments': {'path': 'calc.py', 'content': _FIXED_SRC},
                    'call_id': 'fix-write',
                }
            ),
            '{"type":"final","content":"done"}',
        ]
    )

    run_out = io.StringIO()
    run_err = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
        redirect_stderr(run_err),
    ):
        exit_code = main(
            [
                'agent',
                'run',
                'gpt',
                'Fix the bug in calc.py',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'prompt',
                '--require-plan',  # gate active
                '--max-iterations',
                '4',
                '--max-tool-calls',
                '4',
            ]
        )

    assert exit_code == 2, (
        f'Plan gate must return exit code 2, got {exit_code}; '
        f'stderr: {run_err.getvalue()}'
    )

    # U-P1-2: the plan-gate denial routes through format_error_block on stderr
    # (with a hint), not raw JSON on stdout.
    assert run_out.getvalue().strip() == '', 'Plan gate must not write to stdout'
    gate_err = run_err.getvalue()
    assert 'PLAN_GATE' in gate_err, 'Gate error must be categorized PLAN_GATE'
    assert 'plan' in gate_err.lower(), 'Error message must mention plan requirement'

    assert 'a - b' in calc.read_text(encoding='utf-8'), (
        'Plan gate must prevent any file mutation'
    )


# ---------------------------------------------------------------------------
# Test 2: Full governed run — the core proof
# ---------------------------------------------------------------------------


def test_proof_steps2_through_6_full_governed_run(tmp_path: Path) -> None:
    """End-to-end governance proof: plan → approval → edit → verify → receipt → undo."""
    calc, plan_file = _setup_workspace(tmp_path)
    _git_baseline(tmp_path)  # enables git-sandbox rollback for undo step
    plan_contract = load_plan_contract(plan_file, root=tmp_path)

    adapter = FakeAdapter(list(_FAKE_RESPONSES))

    # ── Steps 2–4: governed agent run ─────────────────────────────────────
    # Compute digest for the write approval
    from teaagent.policy import compute_scoped_payload_digest

    write_args = {'path': 'calc.py', 'content': _FIXED_SRC}
    write_digest = compute_scoped_payload_digest('workspace_write_file', write_args)

    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'agent',
                'run',
                'gpt',
                'Fix the bug in calc.py',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'prompt',
                '--from-plan',
                str(plan_file),
                '--allow-external-plan',
                '--require-plan',
                '--git-sandbox-auto-stash',
                '--approve-scoped',
                f'workspace_write_file:{write_digest}',
                '--max-iterations',
                '8',
                '--max-tool-calls',
                '8',
            ]
        )

    run_payload = json.loads(run_out.getvalue())
    assert run_code == 0, f'Governed run must succeed; got: {run_payload}'
    assert run_payload['status'] == 'completed'

    # Step 3: file was mutated correctly
    assert 'a + b' in calc.read_text(encoding='utf-8'), (
        'Agent must have applied the subtraction→addition fix'
    )

    # Plan integrity preserved
    assert run_payload['plan_contract']['content_hash'] == plan_contract.content_hash, (
        'Plan hash in payload must match the file on disk'
    )

    # Step 2: approval was recorded in evidence
    assert run_payload['run_evidence']['approvals'], (
        'Approval must be captured in run evidence'
    )
    approval = run_payload['run_evidence']['approvals'][0]
    # run_evidence uses the RunEvidenceBundle ApprovalEvidence shape:
    # approved (bool), auto_approved, authority_type, approved_by
    assert approval.get('approved') is True, (
        f'Approval must be marked approved; got: {approval}'
    )

    # ── Step 5: evidence receipt ───────────────────────────────────────────
    store = RunStore(tmp_path)
    run_id = run_payload['run_id']
    receipt = build_run_receipt(store, run_id, tmp_path)

    missing = check_receipt_completeness(receipt, include_plan=True)
    assert missing == [], f'Receipt is missing required sections: {missing}'

    assert 'workspace_write_file: granted' in receipt, (
        'Receipt must show the approved write'
    )
    assert 'Permission mode: prompt' in receipt
    assert f'Plan: {plan_contract.rel_path}' in receipt
    assert 'calc.py fixed' in receipt, 'Receipt must include the final answer'
    assert 'Audit log:' in receipt, 'Receipt must reference the audit log path'
    assert '.teaagent' in receipt, 'Audit log path must be under .teaagent/'

    # ── Step 6: undo restores workspace ───────────────────────────────────
    undo_out = io.StringIO()
    with redirect_stdout(undo_out):
        undo_code = main(
            [
                'agent',
                'undo',
                run_id,
                '--root',
                str(tmp_path),
            ]
        )

    undo_payload = json.loads(undo_out.getvalue())
    assert undo_code == 0, f'Undo must succeed; got: {undo_payload}'
    assert undo_payload['status'] == 'restored', (
        f'Undo status must be "restored", got: {undo_payload}'
    )
    assert 'a - b' in calc.read_text(encoding='utf-8'), (
        'Undo must restore the original (buggy) file'
    )


# ---------------------------------------------------------------------------
# Test 3: Evidence bundle path is reachable from the receipt
# ---------------------------------------------------------------------------


def test_proof_step5_receipt_includes_evidence_bundle_path(tmp_path: Path) -> None:
    """The receipt must include an Audit log: path so the evidence bundle can be
    located by any operator reviewing the run."""
    _, plan_file = _setup_workspace(tmp_path)

    adapter = FakeAdapter(list(_FAKE_RESPONSES))
    # Compute digest for the write approval
    from teaagent.policy import compute_scoped_payload_digest

    write_args = {'path': 'calc.py', 'content': _FIXED_SRC}
    write_digest = compute_scoped_payload_digest('workspace_write_file', write_args)

    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        main(
            [
                'agent',
                'run',
                'gpt',
                'Fix the bug in calc.py',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'prompt',
                '--from-plan',
                str(plan_file),
                '--allow-external-plan',
                '--require-plan',
                '--approve-scoped',
                f'workspace_write_file:{write_digest}',
                '--max-iterations',
                '8',
                '--max-tool-calls',
                '8',
            ]
        )

    run_payload = json.loads(run_out.getvalue())
    assert run_payload.get('status') == 'completed', (
        f'Run must complete before checking receipt; got: {run_payload}'
    )

    store = RunStore(tmp_path)
    receipt = build_run_receipt(store, run_payload['run_id'], tmp_path)

    # The audit log line must point to a real file
    for line in receipt.splitlines():
        if line.startswith('Audit log:'):
            audit_path_str = line.split('Audit log:', 1)[1].strip()
            audit_path = Path(audit_path_str)
            assert audit_path.exists(), (
                f'Audit log path in receipt must exist: {audit_path_str}'
            )
            break
    else:
        raise AssertionError('Receipt must contain an "Audit log:" line')
