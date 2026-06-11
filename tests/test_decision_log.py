from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.decision_log import DecisionLog


def test_add_and_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = DecisionLog(tmp)
        log.add(decision='Use JSONL for audit', reason='Simplicity')
        log.add(
            decision='Block destructive tools by default',
            reason='Safety first',
            do_not_reverse='After security review',
        )
        decisions = log.list()
        assert len(decisions) == 2
        assert decisions[0]['decision'] == 'Use JSONL for audit'
        assert decisions[0]['reason'] == 'Simplicity'
        assert 'do_not_reverse' not in decisions[0]
        assert decisions[1]['do_not_reverse'] == 'After security review'


def test_recent_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = DecisionLog(tmp)
        for i in range(5):
            log.add(decision=f'Decision {i}', reason=f'Reason {i}')
        assert len(log.recent(limit=3)) == 3
        recent = log.recent(limit=3)
        assert recent[0]['decision'] == 'Decision 4'
        assert recent[1]['decision'] == 'Decision 3'


def test_inject_summary_format() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = DecisionLog(tmp)
        log.add(decision='Use JSONL for audit', reason='Simplicity')
        summary = log.inject_summary()
        assert '## Recent Decisions' in summary
        assert '**Decision:** Use JSONL for audit' in summary
        assert '**Reason:** Simplicity' in summary


def test_inject_summary_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = DecisionLog(tmp)
        assert log.inject_summary() == ''


def test_inject_summary_truncation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = DecisionLog(tmp)
        log.add(decision='A' * 500, reason='B' * 500)
        summary = log.inject_summary(max_chars=100)
        assert len(summary) <= 110


def test_empty_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = DecisionLog(tmp)
        assert log.list() == []


def test_cli_decisions_add_and_list() -> None:
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
        assert add_code == 0
        add_payload = json.loads(add_output.getvalue())
        assert add_payload['status'] == 'created'

        list_output = io.StringIO()
        with redirect_stdout(list_output):
            list_code = main(['memory', 'decisions', 'list', '--root', tmp])
        assert list_code == 0
        decisions = json.loads(list_output.getvalue())
        assert len(decisions) == 1
        assert decisions[0]['decision'] == 'Use prompt mode for risky edits'


def test_cli_decisions_add_with_dont_reverse() -> None:
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
        assert add_code == 0
        list_output = io.StringIO()
        with redirect_stdout(list_output):
            main(['memory', 'decisions', 'list', '--root', tmp])
        decisions = json.loads(list_output.getvalue())
        assert decisions[0]['do_not_reverse'] == 'Without legal approval'
