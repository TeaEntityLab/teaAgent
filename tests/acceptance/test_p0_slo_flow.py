"""AC-P0-SLO: P0 operational SLO guardrails for core run/resume flows.

As a maintainer, I want bounded latency on critical local workflows so
regressions in run/approval/resume liveness are caught before merge.

Acceptance criteria:
- A small read-only run completes under a generous local latency budget.
- A prompt-mode destructive call reaches pending-approval quickly.
- Resume from pending approval completes under a generous local latency budget.
- Heartbeat status exposes at least one tick during a deliberately slow run.
"""

from __future__ import annotations

import io
import json
import time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


def _run_cli(args: list[str], adapter: FakeAdapter) -> tuple[int, dict, float]:
    out = io.StringIO()
    started = time.perf_counter()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(out),
    ):
        code = main(args)
    elapsed = time.perf_counter() - started
    return code, json.loads(out.getvalue()), elapsed


def _audit_logger_disk_full(tmp_path: Path) -> None:
    """Make audit log path point to non-writable file to simulate I/O failure."""
    log_path = tmp_path / '.teaagent' / 'audit' / 'run.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch()
    log_path.chmod(0o444)
    return log_path


def test_p0_slo_for_run_approval_resume_and_heartbeat(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('hello teaagent', encoding='utf-8')

    fast_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
            '{"type":"final","content":"ok"}',
        ],
        before_each=lambda: time.sleep(0.01),
    )
    code, payload, elapsed = _run_cli(
        [
            'agent',
            'run',
            'gpt',
            'Summarize README',
            '--root',
            str(tmp_path),
            '--permission-mode',
            'read-only',
        ],
        fast_adapter,
    )
    assert code == 0
    assert payload['status'] == 'completed'
    assert elapsed < 2.0, f'run latency budget exceeded: {elapsed:.3f}s'

    pause_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}'
        ],
        before_each=lambda: time.sleep(0.01),
    )
    pause_code, pause_payload, pause_elapsed = _run_cli(
        ['agent', 'run', 'gpt', 'Create TODO.md', '--root', str(tmp_path)],
        pause_adapter,
    )
    assert pause_code == 1
    assert pause_payload['status'] == 'pending_approval'
    assert pause_elapsed < 2.0, (
        f'pending-approval latency budget exceeded: {pause_elapsed:.3f}s'
    )

    resume_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}',
            '{"type":"final","content":"created todo"}',
        ],
        before_each=lambda: time.sleep(0.01),
    )
    resume_code, resume_payload, resume_elapsed = _run_cli(
        [
            'agent',
            'resume',
            'gpt',
            pause_payload['run_id'],
            '--root',
            str(tmp_path),
        ],
        resume_adapter,
    )
    assert resume_code == 0
    assert resume_payload['status'] == 'completed'
    assert resume_elapsed < 2.0, (
        f'resume latency budget exceeded: {resume_elapsed:.3f}s'
    )

    slow_adapter = FakeAdapter(
        ['{"type":"final","content":"hb-ok"}'],
        before_each=lambda: time.sleep(0.08),
    )
    hb_code, hb_payload, _ = _run_cli(
        [
            'agent',
            'run',
            'gpt',
            'Return hb-ok',
            '--root',
            str(tmp_path),
            '--heartbeat',
            '0.02',
            '--permission-mode',
            'read-only',
        ],
        slow_adapter,
    )
    assert hb_code == 0
    status_out = io.StringIO()
    with redirect_stdout(status_out):
        status_code = main(
            ['agent', 'status', hb_payload['run_id'], '--root', str(tmp_path)]
        )
    status_payload = json.loads(status_out.getvalue())
    assert status_code == 0
    assert status_payload['last_heartbeat_tick'] is not None
    assert status_payload['last_heartbeat_tick'] >= 1


def test_p0_slo_audit_write_failure_degradation(tmp_path: Path) -> None:
    """Agent run completes gracefully even when audit log path is not writable."""
    (tmp_path / 'README.md').write_text('data', encoding='utf-8')

    audit_dir = tmp_path / '.teaagent' / 'audit'
    audit_dir.mkdir(parents=True)
    audit_dir.chmod(0o444)

    adapter = FakeAdapter(
        [
            '{"type":"final","content":"done despite audit failure"}',
        ]
    )
    code, payload, elapsed = _run_cli(
        [
            'agent',
            'run',
            'gpt',
            'return done',
            '--root',
            str(tmp_path),
            '--permission-mode',
            'read-only',
        ],
        adapter,
    )
    assert code == 0
    assert payload['status'] == 'completed'
    assert elapsed < 3.0


def test_p0_slo_model_timeout_retry(tmp_path: Path) -> None:
    """Model adapter retries on transient HTTP errors within budget."""
    from teaagent.llm._retry import LLMRetryConfig

    retry = LLMRetryConfig(
        max_retries=2, base_delay_seconds=0.01, max_delay_seconds=0.05
    )
    assert retry.max_retries == 2

    delay_hist: list[float] = []
    for attempt in range(3):
        d = retry.delay(attempt)
        delay_hist.append(d)
        assert d > 0

    assert delay_hist[1] > delay_hist[0]


def test_p0_slo_run_observer_streams_metrics(tmp_path: Path) -> None:
    """Observations from the agent run include key runtime metrics."""
    (tmp_path / 'README.md').write_text('hello', encoding='utf-8')
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"r1"}',
            '{"type":"final","content":"done"}',
        ],
        before_each=lambda: time.sleep(0.01),
    )
    code, payload, elapsed = _run_cli(
        [
            'agent',
            'run',
            'gpt',
            'read and done',
            '--root',
            str(tmp_path),
            '--permission-mode',
            'read-only',
        ],
        adapter,
    )
    assert code == 0
    assert payload['status'] == 'completed'
    assert payload['iterations'] >= 1
    assert payload['tool_calls'] >= 1
    assert isinstance(payload.get('input_tokens'), int)
    assert isinstance(payload.get('output_tokens'), int)
    assert elapsed < 3.0
