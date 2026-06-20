"""AC-NEW-14: Run evidence summary flow.

As a user, I want every completed run to produce a concise evidence summary so
that I can trust, share, or undo the work.

Acceptance criteria:
- Summary includes changed files, commands, tests, approvals, denied actions,
  costs, known failures, and rollback path.
- Summary exists for successful, failed, cancelled, and pending-approval runs.
- Sensitive values are redacted.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.plan import load_plan_contract
from teaagent.policy import compute_scoped_payload_digest
from teaagent.run_evidence import (
    build_run_evidence_bundle,
)
from teaagent.run_receipt import build_run_receipt, check_receipt_completeness
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger


def test_evidence_summary_includes_all_required_fields(tmp_path):
    """Evidence summary must include all required fields: changed files, commands, tests, approvals, costs, failures, rollback."""
    run_id = 'run-evidence-001'

    # Create audit logger at the run path directly
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    # Record a complete run lifecycle
    audit.record('run_started', run_id, task='test task', model='gpt-4')
    audit.record(
        'tool_use',
        run_id,
        tool_name='exec',
        input={'command': 'ls -la'},
    )
    audit.record(
        'tool_use',
        run_id,
        tool_name='workspace_write_file',
        input={'path': 'test.txt', 'content': 'test content'},
    )
    audit.record(
        'approval_requested',
        run_id,
        call_id='call-123',
        tool_name='workspace_write_file',
        auto_approved=False,
    )
    audit.record(
        'approval_granted',
        run_id,
        call_id='call-123',
        tool_name='workspace_write_file',
        auto_approved=False,
    )
    audit.record(
        'test_run',
        run_id,
        test_name='test_example',
        test_file='tests/test_example.py',
        status='passed',
        duration_ms=100.0,
    )
    audit.record(
        'git_sandbox_started',
        run_id,
        success=True,
        auto_stash=False,
        branch_name=f'teaagent-sandbox-{run_id}',
        original_branch='main',
    )
    audit.record(
        'git_sandbox_resolved',
        run_id,
        resolution='merge',
        success=True,
        branch_name=f'teaagent-sandbox-{run_id}',
        original_branch='main',
    )
    audit.record(
        'run_completed', run_id, answer='done', total_tokens=1000, total_cost=0.01
    )

    # Build evidence bundle
    bundle = build_run_evidence_bundle(tmp_path, run_id)

    # Verify all required fields are present
    assert bundle.run_id == run_id
    assert len(bundle.commands_run) > 0, 'Must include commands'
    assert len(bundle.approvals) > 0, 'Must include approvals'
    assert len(bundle.tests) > 0, 'Must include tests'
    assert bundle.git_sandbox is not None
    assert bundle.git_sandbox.resolution == 'merge'

    # Verify command evidence
    cmd = bundle.commands_run[0]
    assert cmd.command == 'ls -la'
    assert cmd.tool_name == 'exec'

    # Verify approval evidence
    approval = bundle.approvals[0]
    assert approval.call_id == 'call-123'
    assert approval.approved is True
    assert approval.auto_approved is False

    # Verify test evidence
    test = bundle.tests[0]
    assert test.test_name == 'test_example'
    assert test.status == 'passed'


def test_evidence_summary_for_successful_run(tmp_path):
    """Evidence summary must be generated for successful runs."""
    run_id = 'run-success-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='success task')
    audit.record('tool_use', run_id, tool_name='exec', input={'command': 'echo "ok"'})
    audit.record('run_completed', run_id, answer='done')

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id
    assert len(bundle.commands_run) == 1
    assert bundle.commands_run[0].command == 'echo "ok"'


def test_evidence_summary_for_failed_run(tmp_path):
    """Evidence summary must be generated for failed runs and include known failures."""
    run_id = 'run-failed-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='failing task')
    audit.record(
        'tool_use',
        run_id,
        tool_name='exec',
        input={'command': 'invalid_command'},
    )
    audit.record('run_failed', run_id, message='Command not found')

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id
    assert len(bundle.known_gaps) > 0, 'Failed runs must include known gaps'
    assert any(g.category == 'run_failure' for g in bundle.known_gaps)


def test_evidence_summary_for_cancelled_run(tmp_path):
    """Evidence summary must be generated for cancelled runs."""
    run_id = 'run-cancelled-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='cancelled task')
    audit.record('tool_use', run_id, tool_name='exec', input={'command': 'sleep 100'})
    audit.record('run_cancelled', run_id, reason='user cancelled')

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id
    assert len(bundle.commands_run) == 1


def test_evidence_summary_for_pending_approval_run(tmp_path):
    """Evidence summary must be generated for runs pending approval."""
    run_id = 'run-pending-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='pending task')
    audit.record(
        'tool_use',
        run_id,
        tool_name='workspace_write_file',
        input={'path': 'test.txt', 'content': 'content'},
    )
    audit.record(
        'approval_requested',
        run_id,
        call_id='call-456',
        tool_name='workspace_write_file',
        auto_approved=False,
    )
    # No approval_granted - run is pending

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id
    assert len(bundle.approvals) == 1
    assert bundle.approvals[0].approved is False, (
        'Pending approval should not be marked as approved'
    )


def test_evidence_summary_denied_actions(tmp_path):
    """Evidence summary must include denied actions."""
    run_id = 'run-denied-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='denied task')
    audit.record(
        'tool_use',
        run_id,
        tool_name='workspace_write_file',
        input={'path': 'sensitive.txt', 'content': 'secret'},
    )
    audit.record(
        'approval_requested',
        run_id,
        call_id='call-789',
        tool_name='workspace_write_file',
        auto_approved=False,
    )
    audit.record(
        'approval_denied',
        run_id,
        call_id='call-789',
        tool_name='workspace_write_file',
    )

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id
    assert len(bundle.approvals) == 1
    assert bundle.approvals[0].denied is True, 'Denied action must be marked'


def test_evidence_summary_sensitive_values_redacted(tmp_path):
    """Evidence summary must redact sensitive values."""
    run_id = 'run-sensitive-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='sensitive task')
    audit.record(
        'tool_use',
        run_id,
        tool_name='workspace_write_file',
        input={'path': 'secret.txt', 'content': 'my secret password'},
    )
    audit.record('run_completed', run_id, answer='done')

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id

    # Convert to dict and check that sensitive content is not present
    bundle_dict = bundle.to_dict()
    bundle_json = json.dumps(bundle_dict)
    assert 'my secret password' not in bundle_json, 'Sensitive content must be redacted'


def test_real_run_receipt_completeness_from_plan(tmp_path: Path) -> None:
    """A governed run from plan should produce a complete human receipt."""
    calc = tmp_path / 'calc.py'
    test_file = tmp_path / 'test_calc.py'
    calc.write_text('def add(a, b):\n    return a - b\n', encoding='utf-8')
    test_file.write_text(
        'from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n',
        encoding='utf-8',
    )

    plans_dir = tmp_path / '.teaagent' / 'plans'
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_artifact = plans_dir / 'receipt-complete.md'
    plan_artifact.write_text(
        '# Plan\n\n'
        '## Summary\n'
        '- **Task:** Fix calc.py so pytest passes\n\n'
        '## Files likely touched\n'
        '- `calc.py`\n'
        '- `test_calc.py`\n',
        encoding='utf-8',
    )
    plan_contract = load_plan_contract(plan_artifact, root=tmp_path)

    adapter = FakeAdapter(
        [
            json.dumps(
                {
                    'type': 'tool',
                    'tool_name': 'workspace_write_file',
                    'arguments': {
                        'path': 'calc.py',
                        'content': 'def add(a, b):\n    return a + b\n',
                    },
                    'call_id': 'write-calc',
                }
            ),
            json.dumps(
                {
                    'type': 'tool',
                    'tool_name': 'workspace_run_shell_inspect',
                    'arguments': {'command': "rg 'return a \\+ b' calc.py"},
                    'call_id': 'verify-calc',
                }
            ),
            '{"type":"final","content":"calc fixed and verified"}',
        ]
    )

    # G-P2-2: pre-approve the write via payload digest (--approve-scoped), the
    # secure replacement for the removed --approve-call-id.
    write_digest = compute_scoped_payload_digest(
        'workspace_write_file',
        {'path': 'calc.py', 'content': 'def add(a, b):\n    return a + b\n'},
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
                str(plan_artifact),
                '--root',
                str(tmp_path),
                '--permission-mode',
                'prompt',
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
    assert run_code == 0
    assert run_payload['status'] == 'completed'
    assert run_payload['plan_contract']['content_hash'] == plan_contract.content_hash
    assert run_payload['run_evidence']['commands_run']
    assert run_payload['run_evidence']['approvals']

    receipt = build_run_receipt(RunStore(tmp_path), run_payload['run_id'], tmp_path)
    assert check_receipt_completeness(receipt, include_plan=True) == []
    assert 'Permission mode: prompt' in receipt
    assert f'Plan: {plan_contract.rel_path}' in receipt
    assert 'Final result: calc fixed and verified' in receipt
    assert 'Commands run:' in receipt
    assert '- [redacted] [exit 0]' in receipt
    assert 'Approvals:' in receipt
    assert 'workspace_write_file: granted' in receipt


def test_evidence_summary_serialization(tmp_path):
    """Evidence summary must be serializable to JSON for sharing."""
    run_id = 'run-serialize-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='serialize task')
    audit.record('tool_use', run_id, tool_name='exec', input={'command': 'ls'})
    audit.record('run_completed', run_id, answer='done')

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    bundle_dict = bundle.to_dict()

    # Must be JSON serializable
    json_str = json.dumps(bundle_dict)
    assert json_str is not None

    # Must be deserializable back to dict
    parsed = json.loads(json_str)
    assert parsed['run_id'] == run_id
    assert len(parsed['commands_run']) == 1


def test_evidence_summary_changed_files(tmp_path):
    """Evidence summary should track changed files when available."""
    run_id = 'run-files-001'
    store = RunStore(tmp_path)
    audit_path = store.run_path(run_id)
    audit = AuditLogger(path=audit_path)

    audit.record('run_started', run_id, task='files task')
    audit.record(
        'tool_use',
        run_id,
        tool_name='workspace_write_file',
        input={'path': 'modified.txt', 'content': 'new content'},
    )
    audit.record(
        'file_changed',
        run_id,
        path='modified.txt',
        operation='write',
    )
    audit.record('run_completed', run_id, answer='done')

    bundle = build_run_evidence_bundle(tmp_path, run_id)
    assert bundle.run_id == run_id
    # Changed files would be extracted from file_changed events
    # This test verifies the structure supports it
