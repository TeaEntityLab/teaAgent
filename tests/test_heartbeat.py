from __future__ import annotations

import io
import json
import time
from contextlib import redirect_stdout

from conftest import FakeAdapter

from teaagent import (
    AuditLogger,
    ChatAgentConfig,
    Heartbeat,
    RunStore,
    run_chat_agent,
)
from teaagent.cli import main


def test_tick_records_audit_event() -> None:
    audit = AuditLogger()
    beat = Heartbeat(audit, 'run-1', interval_seconds=0.05)

    beat.tick()
    beat.tick()

    types = [event.event_type for event in audit.events]
    assert types == ['heartbeat', 'heartbeat']
    assert audit.events[-1].payload['tick'] == 2


def test_thread_loop_emits_at_least_one_heartbeat() -> None:
    audit = AuditLogger()
    with Heartbeat(audit, 'run-loop', interval_seconds=0.02):
        time.sleep(0.1)
    ticks = [event for event in audit.events if event.event_type == 'heartbeat']
    assert len(ticks) >= 1


def test_run_chat_agent_emits_heartbeat_when_configured(
    chat_agent_config: ChatAgentConfig,
    fake_adapter_with_final_response: FakeAdapter,
    tmp_run_store: RunStore,
) -> None:
    adapter = FakeAdapter(
        ['{"type":"final","content":"done"}'],
        before_each=lambda: time.sleep(0.05),
    )
    audit = tmp_run_store.audit_logger()

    result = run_chat_agent(
        ChatAgentConfig.from_root(chat_agent_config.root, heartbeat_seconds=0.02),
        'long task',
        adapter=adapter,
        audit=audit,
    )

    tmp_run_store.logger_for_result(result, audit)
    assert result.status == 'completed'
    assert sum(1 for event in audit.events if event.event_type == 'heartbeat') >= 1


def test_run_store_heartbeat_for_run_reports_running_until_terminal(
    tmp_run_store: RunStore,
) -> None:
    audit = tmp_run_store.audit_logger('run-hb')
    audit.record('run_started', 'run-hb', task='t')
    audit.record('heartbeat', 'run-hb', tick=1, interval_seconds=0.1)

    running = tmp_run_store.heartbeat_for_run('run-hb')
    assert running['status'] == 'running'
    assert running['last_heartbeat_at'] is not None
    assert running['last_heartbeat_tick'] == 1

    audit.record('run_completed', 'run-hb', answer='x', metadata={})
    done = tmp_run_store.heartbeat_for_run('run-hb')
    assert done['status'] == 'completed'


def test_cli_agent_status_returns_heartbeat_liveness(
    tmp_run_store: RunStore,
    chat_agent_config: ChatAgentConfig,
) -> None:
    audit = tmp_run_store.audit_logger('cli-hb')
    audit.record('run_started', 'cli-hb', task='t')
    audit.record('heartbeat', 'cli-hb', tick=1, interval_seconds=0.1)
    audit.record('run_completed', 'cli-hb', answer='x', metadata={})

    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            ['agent', 'status', 'cli-hb', '--root', str(chat_agent_config.root)]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['last_heartbeat_tick'] == 1
    assert payload['status'] == 'completed'
