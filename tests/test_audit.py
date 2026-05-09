from __future__ import annotations

import json
import stat
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from teaagent.audit import (
    AUDIT_DIR_MODE,
    AUDIT_FILE_MODE,
    AUDIT_REDACTED,
    AUDIT_TRUNCATED,
    MAX_AUDIT_STRING_LENGTH,
    AuditEvent,
    AuditLogger,
    utc_now,
)


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


class AuditEventTests(unittest.TestCase):
    def test_event_has_default_fields(self) -> None:
        event = AuditEvent(
            event_type='test_event', run_id='run-1', payload={'key': 'val'}
        )

        self.assertEqual(event.event_type, 'test_event')
        self.assertEqual(event.run_id, 'run-1')
        self.assertEqual(event.payload, {'key': 'val'})
        self.assertTrue(len(event.event_id) > 0)
        self.assertTrue(len(event.created_at) > 0)

    def test_event_can_override_event_id(self) -> None:
        event = AuditEvent(event_type='e', run_id='r', payload={}, event_id='custom-id')

        self.assertEqual(event.event_id, 'custom-id')

    def test_to_json_produces_valid_json(self) -> None:
        event = AuditEvent(event_type='e', run_id='r', payload={})
        payload = json.loads(event.to_json())

        self.assertEqual(payload['event_type'], 'e')
        self.assertEqual(payload['run_id'], 'r')
        self.assertIn('event_id', payload)
        self.assertIn('created_at', payload)
        self.assertIn('payload', payload)

    def test_event_is_frozen(self) -> None:
        event = AuditEvent(event_type='e', run_id='r', payload={})
        with self.assertRaises(FrozenInstanceError):
            event.run_id = 'other'  # type: ignore[misc]


class AuditLoggerTests(unittest.TestCase):
    def test_record_stores_event_in_memory(self) -> None:
        logger = AuditLogger()
        event = logger.record('test_event', 'run-1', key='value')

        self.assertEqual(event.event_type, 'test_event')
        self.assertEqual(event.run_id, 'run-1')
        self.assertEqual(event.payload, {'key': 'value'})
        self.assertEqual(len(logger.events), 1)
        self.assertIs(logger.events[0], event)

    def test_record_multiple_events_in_order(self) -> None:
        logger = AuditLogger()
        logger.record('start', 'r1')
        logger.record('end', 'r1')

        self.assertEqual(len(logger.events), 2)
        self.assertEqual(logger.events[0].event_type, 'start')
        self.assertEqual(logger.events[1].event_type, 'end')

    def test_sink_receives_every_recorded_event(self) -> None:
        logger = AuditLogger()
        received = []

        logger.add_sink(received.append)
        e1 = logger.record('a', 'r1')
        e2 = logger.record('b', 'r1')

        self.assertEqual(received, [e1, e2])

    def test_multiple_sinks_receive_events(self) -> None:
        logger = AuditLogger()
        sink1: list[AuditEvent] = []
        sink2: list[AuditEvent] = []

        logger.add_sink(sink1.append)
        logger.add_sink(sink2.append)
        event = logger.record('e', 'r')

        self.assertEqual(len(sink1), 1)
        self.assertEqual(len(sink2), 1)
        self.assertIs(sink1[0], event)
        self.assertIs(sink2[0], event)

    def test_persists_events_to_jsonl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit.jsonl'
            logger = AuditLogger(path=path)

            logger.record('e1', 'r1', a=1)
            logger.record('e2', 'r1', b=2)

            lines = path.read_text(encoding='utf-8').strip().split('\n')
            self.assertEqual(len(lines), 2)

            e1 = json.loads(lines[0])
            e2 = json.loads(lines[1])
            self.assertEqual(e1['event_type'], 'e1')
            self.assertEqual(e1['payload'], {'a': 1})
            self.assertEqual(e2['event_type'], 'e2')
            self.assertEqual(e2['payload'], {'b': 2})

    def test_threaded_persistence_writes_complete_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit.jsonl'
            logger = AuditLogger(path=path)

            def write_events(start: int) -> None:
                for i in range(start, start + 25):
                    logger.record('e', 'r', index=i)

            threads = [
                threading.Thread(target=write_events, args=(i * 25,)) for i in range(4)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            lines = path.read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines), 100)
            for line in lines:
                self.assertEqual(json.loads(line)['event_type'], 'e')

    def test_record_redacts_sensitive_payload_keys(self) -> None:
        logger = AuditLogger()

        event = logger.record(
            'tool_call_started',
            'run-1',
            arguments={
                'api_key': 'sk-secret',
                'nested': {'Authorization': 'Bearer secret'},
                'path': 'file.txt',
            },
        )

        self.assertEqual(event.payload['arguments']['api_key'], AUDIT_REDACTED)
        self.assertEqual(
            event.payload['arguments']['nested']['Authorization'], AUDIT_REDACTED
        )
        self.assertEqual(event.payload['arguments']['path'], 'file.txt')

    def test_record_redacts_sensitive_tool_argument_values(self) -> None:
        logger = AuditLogger()

        event = logger.record(
            'tool_call_started',
            'run-1',
            arguments={
                'path': 'file.txt',
                'content': 'secret file body',
                'old': 'previous secret',
                'new': 'new secret',
                'command': 'export TOKEN=secret',
            },
        )

        self.assertEqual(event.payload['arguments']['path'], 'file.txt')
        self.assertEqual(event.payload['arguments']['content'], AUDIT_REDACTED)
        self.assertEqual(event.payload['arguments']['old'], AUDIT_REDACTED)
        self.assertEqual(event.payload['arguments']['new'], AUDIT_REDACTED)
        self.assertEqual(event.payload['arguments']['command'], AUDIT_REDACTED)

    def test_record_preserves_non_argument_content(self) -> None:
        logger = AuditLogger()

        event = logger.record('tool_call_completed', 'run-1', content='read result')

        self.assertEqual(event.payload['content'], 'read result')

    def test_record_redacts_sensitive_tool_result_values(self) -> None:
        logger = AuditLogger()

        event = logger.record(
            'tool_call_completed',
            'run-1',
            tool_name='workspace_read_file',
            result={
                'path': 'file.txt',
                'content': 'secret file body',
                'truncated': False,
                'matches': [{'line': 1, 'text': 'secret match'}],
                'stdout': 'secret stdout',
                'stderr': 'secret stderr',
            },
        )

        result = event.payload['result']
        self.assertEqual(result['path'], 'file.txt')
        self.assertFalse(result['truncated'])
        self.assertEqual(result['content'], AUDIT_REDACTED)
        self.assertEqual(result['matches'][0]['line'], 1)
        self.assertEqual(result['matches'][0]['text'], AUDIT_REDACTED)
        self.assertEqual(result['stdout'], AUDIT_REDACTED)
        self.assertEqual(result['stderr'], AUDIT_REDACTED)

    def test_record_truncates_large_strings(self) -> None:
        logger = AuditLogger()

        event = logger.record(
            'tool_call_completed', 'run-1', stdout='x' * (MAX_AUDIT_STRING_LENGTH + 1)
        )

        self.assertEqual(
            len(event.payload['stdout']), MAX_AUDIT_STRING_LENGTH + len(AUDIT_TRUNCATED)
        )
        self.assertTrue(event.payload['stdout'].endswith(AUDIT_TRUNCATED))

    def test_path_parent_dirs_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sub' / 'nested' / 'audit.jsonl'
            logger = AuditLogger(path=path)
            logger.record('e', 'r')

            self.assertTrue(path.exists())
            self.assertEqual(file_mode(path.parent), AUDIT_DIR_MODE)
            self.assertEqual(file_mode(path), AUDIT_FILE_MODE)

    def test_in_memory_only_when_no_path(self) -> None:
        logger = AuditLogger()
        logger.record('e', 'r')

        self.assertEqual(len(logger.events), 1)

    def test_thread_safety_concurrent_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit.jsonl'
            logger = AuditLogger(path=path)
            barrier = threading.Barrier(5)

            def record_event(idx: int) -> None:
                barrier.wait()
                logger.record(f'event{idx}', 'r')

            threads = [
                threading.Thread(target=record_event, args=(i,)) for i in range(5)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(logger.events), 5)
            lines = path.read_text(encoding='utf-8').strip().split('\n')
            self.assertEqual(len(lines), 5)


class UtcNowTests(unittest.TestCase):
    def test_returns_isoformat_string(self) -> None:
        ts = utc_now()
        self.assertIsInstance(ts, str)
        self.assertIn('T', ts)
        self.assertIn('+00:00', ts)


if __name__ == '__main__':
    unittest.main()
