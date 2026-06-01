from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.decision_log import DecisionLog


class DecisionLogTests(unittest.TestCase):
    def test_add_and_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(tmp)
            log.add(decision='Use JSONL for audit', reason='Simplicity')
            log.add(
                decision='Block destructive tools by default',
                reason='Safety first',
                do_not_reverse='After security review',
            )
            decisions = log.list()
            self.assertEqual(len(decisions), 2)
            self.assertEqual(decisions[0]['decision'], 'Use JSONL for audit')
            self.assertEqual(decisions[0]['reason'], 'Simplicity')
            self.assertNotIn('do_not_reverse', decisions[0])
            self.assertEqual(decisions[1]['do_not_reverse'], 'After security review')

    def test_recent_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(tmp)
            for i in range(5):
                log.add(decision=f'Decision {i}', reason=f'Reason {i}')
            self.assertEqual(len(log.recent(limit=3)), 3)
            recent = log.recent(limit=3)
            self.assertEqual(recent[0]['decision'], 'Decision 4')
            self.assertEqual(recent[1]['decision'], 'Decision 3')

    def test_inject_summary_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(tmp)
            log.add(decision='Use JSONL for audit', reason='Simplicity')
            summary = log.inject_summary()
            self.assertIn('## Recent Decisions', summary)
            self.assertIn('**Decision:** Use JSONL for audit', summary)
            self.assertIn('**Reason:** Simplicity', summary)

    def test_inject_summary_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(tmp)
            self.assertEqual(log.inject_summary(), '')

    def test_inject_summary_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(tmp)
            log.add(decision='A' * 500, reason='B' * 500)
            summary = log.inject_summary(max_chars=100)
            self.assertLessEqual(len(summary), 110)

    def test_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(tmp)
            self.assertEqual(log.list(), [])

    def test_cli_decisions_add_and_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_output = io.StringIO()
            with redirect_stdout(add_output):
                add_code = main(
                    [
                        'memory',
                        'decisions',
                        'add',
                        'Use prompt mode for risky edits',
                        '--reason',
                        'Protect against accidents',
                        '--root',
                        tmp,
                    ]
                )
            self.assertEqual(add_code, 0)
            add_payload = json.loads(add_output.getvalue())
            self.assertEqual(add_payload['status'], 'created')

            list_output = io.StringIO()
            with redirect_stdout(list_output):
                list_code = main(['memory', 'decisions', 'list', '--root', tmp])
            self.assertEqual(list_code, 0)
            decisions = json.loads(list_output.getvalue())
            self.assertEqual(len(decisions), 1)
            self.assertEqual(
                decisions[0]['decision'], 'Use prompt mode for risky edits'
            )

    def test_cli_decisions_add_with_dont_reverse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_output = io.StringIO()
            with redirect_stdout(add_output):
                add_code = main(
                    [
                        'memory',
                        'decisions',
                        'add',
                        'Enforce two-person review',
                        '--reason',
                        'Compliance',
                        '--dont-reverse',
                        'Without legal approval',
                        '--root',
                        tmp,
                    ]
                )
            self.assertEqual(add_code, 0)
            list_output = io.StringIO()
            with redirect_stdout(list_output):
                main(['memory', 'decisions', 'list', '--root', tmp])
            decisions = json.loads(list_output.getvalue())
            self.assertEqual(decisions[0]['do_not_reverse'], 'Without legal approval')


if __name__ == '__main__':
    unittest.main()
