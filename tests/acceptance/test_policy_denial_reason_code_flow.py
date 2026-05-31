"""AT-040: Denial reason codes appear in audit and CLI explain output."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.run_store import RunStore
from teaagent.runner import RunResult


def test_denied_audit_event_includes_reason_code(tmp_path: Path) -> None:
    run_id = 'run-denial-reason'
    store = RunStore(tmp_path)
    audit = store.audit_logger(run_id)
    audit.record(
        'tool_call_denied',
        run_id,
        call_id='call-deny-1',
        tool_name='workspace_write_file',
        reason_code=DenialReasonCode.READ_ONLY_MODE.value,
    )

    events = store.show_run(run_id)
    denied = [e for e in events if e.get('event_type') == 'tool_call_denied']
    assert len(denied) == 1
    assert denied[0]['payload']['reason_code'] == 'read_only_mode'


def test_why_denied_cli_surfaces_reason_code(tmp_path: Path) -> None:
    run_id = 'run-why-cli'
    store = RunStore(tmp_path)
    audit = store.audit_logger(run_id)
    audit.record(
        'tool_call_denied',
        run_id,
        call_id='call-1',
        tool_name='workspace_write_file',
        reason_code=DenialReasonCode.JIT_NO_APPROVAL.value,
    )
    store.logger_for_result(
        RunResult(
            run_id=run_id,
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['approval', 'why-denied', run_id, '--root', str(tmp_path)])
    assert code == 0
    assert 'jit_no_approval' in out.getvalue()


def test_tool_permission_error_carries_reason_code() -> None:
    exc = ToolPermissionError(
        'blocked',
        reason_code=DenialReasonCode.PLAN_CONTRACT_DENIED,
    )
    assert exc.reason_code == DenialReasonCode.PLAN_CONTRACT_DENIED
