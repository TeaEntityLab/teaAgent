from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
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


class HeartbeatTests(unittest.TestCase):
    def test_tick_records_audit_event(self) -> None:
        audit = AuditLogger()
        beat = Heartbeat(audit, 'run-1', interval_seconds=0.05)

        beat.tick()
        beat.tick()

        types = [event.event_type for event in audit.events]
        self.assertEqual(types, ['heartbeat', 'heartbeat'])
        self.assertEqual(audit.events[-1].payload['tick'], 2)

    def test_thread_loop_emits_at_least_one_heartbeat(self) -> None:
        audit = AuditLogger()
        with Heartbeat(audit, 'run-loop', interval_seconds=0.02):
            time.sleep(0.1)
        ticks = [event for event in audit.events if event.event_type == 'heartbeat']
        self.assertGreaterEqual(len(ticks), 1)

    def test_run_chat_agent_emits_heartbeat_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                ['{"type":"final","content":"done"}'],
                before_each=lambda: time.sleep(0.05),
            )
            store = RunStore(tmp)
            audit = store.audit_logger()

            result = run_chat_agent(
                task='long task',
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp, heartbeat_seconds=0.02),
                audit=audit,
            )

            store.logger_for_result(result, audit)
            self.assertEqual(result.status, 'completed')
            self.assertGreaterEqual(
                sum(1 for event in audit.events if event.event_type == 'heartbeat'),
                1,
            )

    def test_run_store_heartbeat_for_run_reports_running_until_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger('run-hb')
            audit.record('run_started', 'run-hb', task='t')
            audit.record('heartbeat', 'run-hb', tick=1, interval_seconds=0.1)

            running = store.heartbeat_for_run('run-hb')
            self.assertEqual(running['status'], 'running')
            self.assertIsNotNone(running['last_heartbeat_at'])
            self.assertEqual(running['last_heartbeat_tick'], 1)

            audit.record('run_completed', 'run-hb', answer='x', metadata={})
            done = store.heartbeat_for_run('run-hb')
            self.assertEqual(done['status'], 'completed')

    def test_cli_agent_status_returns_heartbeat_liveness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger('cli-hb')
            audit.record('run_started', 'cli-hb', task='t')
            audit.record('heartbeat', 'cli-hb', tick=1, interval_seconds=0.1)
            audit.record('run_completed', 'cli-hb', answer='x', metadata={})

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['agent', 'status', 'cli-hb', '--root', tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload['last_heartbeat_tick'], 1)
            self.assertEqual(payload['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
